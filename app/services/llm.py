import json
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("uvicorn.error")

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        pass


class LMStudioLLMProvider(LLMProvider):
    def __init__(self, api_url: str = "http://localhost:1234/v1/chat/completions"):
        self.api_url = api_url

    def generate(self, prompt: str, system_prompt: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Dynamically fetch the first loaded model name if possible
        model_name = "local-model"
        try:
            models_url = self.api_url.replace("/chat/completions", "/models")
            models_resp = requests.get(models_url, timeout=3)
            if models_resp.status_code == 200:
                models_data = models_resp.json()
                if models_data.get("data") and len(models_data["data"]) > 0:
                    model_name = models_data["data"][0]["id"]
                    logger.info(f"Dynamically detected active LM Studio model: {model_name}")
        except Exception as err:
            logger.warning(f"Could not dynamically query active models from LM Studio: {err}")

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for factual RAG accuracy
            "max_tokens": 1024
        }
        if options:
            payload.update(options)

        try:
            logger.info(f"Calling LM Studio API at {self.api_url}...")
            response = requests.post(self.api_url, json=payload, timeout=60)
            if response.status_code == 200:
                res_json = response.json()
                return res_json["choices"][0]["message"]["content"]
            else:
                logger.error(f"LM Studio returned status {response.status_code}: {response.text}")
                return f"Error: LM Studio returned status {response.status_code}"
        except Exception as e:
            logger.error(f"Failed to connect to LM Studio: {e}")
            return f"Error connecting to LM Studio: {e}. Ensure LM Studio server is running on port 1234."


class AWSBedrockClaudeLLMProvider(LLMProvider):
    def __init__(self, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0", region_name: str = "us-east-1"):
        self.model_id = model_id
        self.region_name = region_name
        self.client = None
        try:
            import boto3
            self.client = boto3.client("bedrock-runtime", region_name=region_name)
        except Exception as e:
            logger.error(f"Failed to initialize AWS Bedrock boto3 client: {e}")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        if not self.client:
            return "Error: AWS Bedrock client not initialized."

        # Anthropic Claude 3 messaging payload schema for Bedrock
        messages = [{"role": "user", "content": prompt}]
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": messages,
            "temperature": 0.1,
        }
        if system_prompt:
            body["system"] = system_prompt
        if options:
            body.update(options)

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )
            response_body = json.loads(response.get("body").read())
            return response_body["content"][0]["text"]
        except Exception as e:
            logger.error(f"AWS Bedrock Claude execution error: {e}")
            return f"Error calling AWS Bedrock Claude: {str(e)}"


class OpenAIChatLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, api_url: str):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url

    def generate(self, prompt: str, system_prompt: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        if not self.api_key:
            return f"Error: API Key for model {self.model} not configured. Please set it in your .env file."
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1024
        }
        if options:
            payload.update(options)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"Calling OpenAI-compatible API at {self.api_url} with model {self.model}...")
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                res_json = response.json()
                return res_json["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API returned status {response.status_code}: {response.text}")
                return f"Error: LLM API returned status {response.status_code} - {response.text}"
        except Exception as e:
            logger.error(f"Failed to connect to LLM API: {e}")
            return f"Error connecting to LLM API: {e}"

