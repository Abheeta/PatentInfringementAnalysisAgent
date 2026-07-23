from app.ai.provider import LLMProvider


class FakeProvider(LLMProvider):
    """Returns canned responses in sequence, one per call to generate().
    Pass a list of dicts (or exceptions to raise) matching how many times
    the code under test is expected to call generate()."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[tuple[list[dict], dict]] = []

    def generate(self, messages: list[dict], schema: dict) -> dict:
        self.calls.append((messages, schema))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
