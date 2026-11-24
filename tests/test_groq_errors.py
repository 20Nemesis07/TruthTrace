import unittest
from unittest.mock import patch
import httpx
from backend.schemas import Findings
from backend.services.gemini_service import interpret, ModelUnavailable

class GroqErrors(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, responses):
        calls = []
        def handle(req):
            calls.append(req.read())
            code, data = responses.pop(0)
            return httpx.Response(code, json=data)
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle),trust_env=False)
        with patch("backend.services.gemini_service.provider",return_value=("groq","openai/gpt-oss-20b","secret")), patch("backend.services.gemini_service.httpx.AsyncClient",return_value=client):
            result = await interpret("Return JSON.",{},Findings)
        return result,calls

    async def test_schema_error_retries_once(self):
        result,calls=await self.exercise([(400,{"error":{"code":"json_validate_failed"}}),(200,{"choices":[{"message":{"content":'{"findings":[]}'}}]})])
        self.assertEqual(result.findings,[])
        self.assertIn(b"response_format",calls[0])
        self.assertNotIn(b"response_format",calls[1])

    async def test_other_400_retains_detail_and_masks_key(self):
        with self.assertRaisesRegex(ModelUnavailable,r"model_decommissioned.*\[redacted\]") as error:
            await self.exercise([(400,{"error":{"code":"model_decommissioned","message":"Model unavailable secret"}})])
        self.assertNotIn("secret",str(error.exception))
