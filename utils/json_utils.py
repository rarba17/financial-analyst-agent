import json
import re


class JSONUtils:
    @staticmethod
    def parse_json_string(json_str: str) -> dict:
        match = re.match(r"^```json\n(.*?)\n```$", json_str, re.DOTALL)
        if match:
            json_str = match.group(1)
        try:
            return json.loads(json_str)
        except Exception as e:
            raise e
