/// <reference path="./.sst/platform/config.d.ts" />
export default $config({
  app(input) {
    return {
      name: "intelliq",
      removal: input?.stage === "production" ? "retain" : "remove",
      protect: ["production"].includes(input?.stage),
      home: "aws",
      providers: { aws: "7.52.1" },
    };
  },
  async run() {
    const region = aws.getRegionOutput().name;
    const stage = $app.stage;
    // -------------------------------------------------------------------------
    // ADR-02: Zero-Cost Secrets & SSM Parameter Store
    // -------------------------------------------------------------------------
    const geminiApiKey = new sst.Secret(
      "GeminiApiKey",
      process.env.GEMINI_API_KEY || "",
    );
    const groqApiKey = new sst.Secret(
      "GroqApiKey",
      process.env.GROQ_API_KEY || "",
    );
    // -------------------------------------------------------------------------
    // ADR-01: Free-Tier S3 Bucket (Zero Orphan Costs Lifecycle)
    // -------------------------------------------------------------------------
    const bucket = new sst.aws.Bucket("Storage", {
      cors: {
        allowHeaders: ["*"],
        allowMethods: ["GET", "PUT", "POST", "HEAD"],
        allowOrigins: ["*"],
        maxAge: "1 day",
      },
      transform: {
        bucket: (args) => {
          args.lifecycleRules = [
            {
              id: "AbortIncompleteMultipartUpload",
              enabled: true,
              abortIncompleteMultipartUploadDays: 1,
            },
            {
              id: "ExpireTemporaryArtifacts",
              enabled: true,
              prefix: "tmp/",
              expirations: [
                {
                  days: 7,
                },
              ],
            },
          ];
        },
      },
    });
    // -------------------------------------------------------------------------
    // ADR-01: DynamoDB Single-Table Free-Tier (10 RCU / 10 WCU Provisioned)
    // -------------------------------------------------------------------------
    const table = new sst.aws.Dynamo("Database", {
      fields: {
        PK: "string",
        SK: "string",
        GSI1PK: "string",
        GSI1SK: "string",
      },
      primaryIndex: { hashKey: "PK", rangeKey: "SK" },
      globalIndexes: {
        GSI1: { hashKey: "GSI1PK", rangeKey: "GSI1SK" },
      },
      ttl: "ttl",
      transform: {
        table: (args) => {
          // Stay well under 25 RCU / 25 WCU Always-Free tier limit
          const isProvisioned =
            process.env.DYNAMODB_BILLING_MODE !== "PAY_PER_REQUEST";
          if (isProvisioned) {
            args.billingMode = "PROVISIONED";
            args.readCapacity = 10;
            args.writeCapacity = 10;
            if (args.globalSecondaryIndexes) {
              for (const gsi of args.globalSecondaryIndexes) {
                gsi.readCapacity = 10;
                gsi.writeCapacity = 10;
              }
            }
          } else {
            args.billingMode = "PAY_PER_REQUEST";
          }
        },
      },
    });
    // -------------------------------------------------------------------------
    // ADR-04: Cognito Lite User Pool ($0 Idle / 10k+ MAU Free Tier)
    // -------------------------------------------------------------------------
    const userPool = new sst.aws.CognitoUserPool("Auth", {
      usernames: ["email"],
      transform: {
        userPool: (args) => {
          // Standard/Lite tier: do NOT enable paid advanced security
          args.userPoolAddOns = undefined;
        },
      },
    });
    const userPoolClient = userPool.addClient("WebClient", {
      transform: {
        client: (args) => {
          args.explicitAuthFlows = [
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
            "ALLOW_USER_SRP_AUTH",
          ];
        },
      },
    });
    // -------------------------------------------------------------------------
    // ADR-05: High-Performance Streaming Lambda (ARM64 Graviton + LWA)
    // -------------------------------------------------------------------------
    const streamWorker = new sst.aws.Function("StreamWorker", {
      runtime: "python3.12",
      architecture: "arm64",
      handler: "lambdas/stream_worker/run.handler",
      memory: "1024 MB",
      timeout: "900 seconds",
      logging: {
        retention: "1 week", // ADR-02: Strict CloudWatch Log Cap
      },
      url: {
        streaming: true,
      },
      link: [table, bucket, geminiApiKey, groqApiKey],
      layers: [
        $interpolate`arn:aws:lambda:${region}:753240598075:layer:LambdaAdapterLayerArm64:24`,
      ],
      environment: {
        PYTHONPATH: "/var/task/intelliq",
        AWS_LAMBDA_EXEC_WRAPPER: "/opt/bootstrap",
        AWS_LWA_INVOKE_MODE: "response_stream",
        AWS_LWA_READINESS_CHECK_PATH: "/api/health",
        AWS_LWA_PORT: "8080",
        TABLE_NAME: table.name,
        BUCKET_NAME: bucket.name,
        COGNITO_USER_POOL_ID: userPool.id,
        COGNITO_CLIENT_ID: userPoolClient.id,
        GEMINI_API_KEY: geminiApiKey.value,
        GEMINI_MODEL: process.env.GEMINI_MODEL || "gemini-3.1-flash-lite",
        GROQ_API_KEY: groqApiKey.value,
        GROQ_MODEL: process.env.GROQ_MODEL || "llama-3.3-70b-versatile",
        ALLOWED_EMAIL_DOMAINS: process.env.ALLOWED_EMAIL_DOMAINS || "*",
      },
    });
    // -------------------------------------------------------------------------
    // Sync CRUD & S3 Presigned URL Lambda
    // -------------------------------------------------------------------------
    const apiHandler = new sst.aws.Function("ApiHandler", {
      runtime: "python3.12",
      architecture: "arm64",
      handler: "lambdas/api_handler/handler.handler",
      memory: "512 MB",
      timeout: "30 seconds",
      logging: {
        retention: "1 week",
      },
      url: true,
      link: [table, bucket, geminiApiKey, groqApiKey],
      environment: {
        PYTHONPATH: "/var/task/intelliq",
        TABLE_NAME: table.name,
        BUCKET_NAME: bucket.name,
        COGNITO_USER_POOL_ID: userPool.id,
        COGNITO_CLIENT_ID: userPoolClient.id,
        ALLOWED_EMAIL_DOMAINS: process.env.ALLOWED_EMAIL_DOMAINS || "*",
      },
    });
    // -------------------------------------------------------------------------
    // ADR-03 & ADR-07: Static Frontend SPA & Single-Domain CloudFront
    // -------------------------------------------------------------------------
    const site = new sst.aws.StaticSite("Frontend", {
      path: "frontend",
      build: {
        command: "npm run build",
        output: "dist",
      },
      environment: {
        VITE_COGNITO_USER_POOL_ID: userPool.id,
        VITE_COGNITO_CLIENT_ID: userPoolClient.id,
        VITE_AWS_REGION: region,
      },
      edge: {
        viewerRequest: undefined,
      },
      invalidation: false, // ADR-07: Instant zero-cost deploys via Cache-Control
    });
    // CloudFront router linking Frontend and Lambda Function URLs
    const router = new sst.aws.Router("EdgeRouter", {
      routes: {
        "/api/stream/*": streamWorker.url,
        "/api/*": apiHandler.url,
        "/*": site.url,
      },
    });
    return {
      region,
      routerUrl: router.url,
      frontendUrl: site.url,
      bucketName: bucket.name,
      tableName: table.name,
      userPoolId: userPool.id,
      userPoolClientId: userPoolClient.id,
      streamWorkerUrl: streamWorker.url,
      apiHandlerUrl: apiHandler.url,
    };
  },
});
