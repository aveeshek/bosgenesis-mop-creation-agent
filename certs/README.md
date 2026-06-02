# Local LLM Certificate Staging

Place local Azure/enterprise SSO certificate files here when needed for development.

Example local files:

```text
Microsoft Azure - SIGMA Non-Prod - Enterprise SSO.cer
Microsoft Azure - SIGMA Non-Prod - Enterprise SSO.xml
```

Real certificate files are intentionally ignored by Git. Keep authentication values in environment variables or approved secret stores.

Sample environment variables for Azure OpenAI access:

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://aiservicesprjbossdcdevh23aw001.openai.azure.com/"
$env:OPENAI_DEPLOYMENT = "bos-trainium-sigma-gpt-4.1-mini"
$env:OPENAI_API_VERSION = "2024-12-01-preview"
```

Use Azure CLI or workload identity for token acquisition where possible.
