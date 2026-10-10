from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from core.config import settings
from llm.open_ai import LLMProvider
import re

def strip_markdown_images(text):
    cleaned_text = re.sub(r'!\[.*?\]\(https?://quickchart\.io[^\s)]+\)', '', text)
    return cleaned_text.strip()


class UnifiedMemoryManager:
    def __init__(
        self,
        thread_id: str,
        max_messages: int = 4,
        summary_token_limit: int = 500,
    ):
        self.session_id = f"user-{thread_id}"
        self.max_messages = max_messages
        self.summary_token_limit = summary_token_limit

        db_user = settings.POSTGRES_USER
        db_password = settings.POSTGRES_PASSWORD
        db_host = settings.POSTGRES_SERVER
        db_port = settings.POSTGRES_PORT
        database = settings.POSTGRES_DB

        self.postgres_connection_string = f"dbname={database} user={db_user} password={db_password} host={db_host} port={db_port}"

        self.chat_history = PostgresChatMessageHistory(
            connection_string=self.postgres_connection_string,
            session_id=self.session_id,
        )
        self.llm_provider = LLMProvider(
            model_name=settings.LLM_MODEL_NAME,
            temperature=1.0,
        )
        self.llm = self.llm_provider.get_llm()

    def get_full_history(self):
        return self.chat_history.messages

    async def get_history_context(self):
        messages = self.chat_history.messages
        if len(messages) > self.max_messages:
            to_summarize = messages[: -self.max_messages]
            recent = messages[-self.max_messages :]
            summary = await self.summarize_messages(to_summarize)
            context = []
            if summary:
                context.append(
                    {
                        "role": "system",
                        "content": f"Summary of previous conversation: {summary}",
                    }
                )
            for msg in recent:
                if msg.type == "human":
                    context.append({"role": "user", "content": msg.content.strip()})
                elif msg.type == "ai":
                    context.append(
                        {"role": "assistant", "content": msg.content.strip()}
                    )
        else:
            context = []
            for msg in messages:
                if msg.type == "human":
                    context.append({"role": "user", "content": msg.content.strip()})
                elif msg.type == "ai":
                    context.append(
                        {"role": "assistant", "content": msg.content.strip()}
                    )

        return context

    async def summarize_messages(self, messages):
        # Convert to LangChain message objects
        conversation_text = []
        for msg in messages:
            if msg.type == "human":
                conversation_text.append(HumanMessage(content=msg.content.strip()))
            elif msg.type == "ai":
                conversation_text.append(AIMessage(content=msg.content.strip()))

        if not conversation_text:
            return ""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"Summarize the following conversation in under {self.summary_token_limit} tokens. Focus on key facts, decisions, and context needed for future turns:\n\n{{conversation}}",
                )
            ]
        )
        chain = prompt | self.llm
        summary_response = await chain.ainvoke({"conversation": conversation_text})
        return summary_response.content.strip()

    def update_memory(
        self, user_query: str, ai_response: str, max_ai_chars: int = 1500
    ):
        self.chat_history.add_user_message(user_query)
        ai_response = strip_markdown_images(ai_response)
        trimmed_response = (
            ai_response[:max_ai_chars] + "\n\n[...truncated]"
            if len(ai_response) > max_ai_chars
            else ai_response
        )
        self.chat_history.add_ai_message(trimmed_response)
