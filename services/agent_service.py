import asyncio
from agent.standalone_agent import GCPLFinancialAgent
from models.models import Message
from schemas import schemas
from services.chat_status_service import chat_status_service
from utils.unified_memory_manager import UnifiedMemoryManager


class AgentService:
    def __init__(self, ai_message_id: str) -> None:
        self.general_agent = GCPLFinancialAgent(ai_message_id=ai_message_id)
        self.ai_message_id = ai_message_id

    async def process_message(
        self,
        user_message: Message,
    ):
        try:
            final_response = await self._run_workflow(user_message)
            return final_response
        except Exception as e:
            print(f"[AgentRouter] Exception occurred: {e}")
            raise

    async def _run_workflow(
        self,
        user_message: Message,
    ):

        memory_manager = UnifiedMemoryManager(thread_id=user_message.thread_id)
        history_context = await memory_manager.get_history_context()

        await chat_status_service.send_status(
            self.ai_message_id, "Understanding the question"
        )

        # General Agent
        response = await self.general_agent.run(
            query=user_message.content,
            history_context=history_context,
        )

        # Update memory with only the user query and final response
        memory_manager.update_memory(
            user_query=user_message.content,
            ai_response=response,
        )

        await chat_status_service.send_response(
            self.ai_message_id,
            {
                "id": self.ai_message_id,
                "content": response,
                "thread_id": user_message.thread_id,
                "is_bot": True,
            },
        )

        return response


async def main():
    agent_service = AgentService(ai_message_id="123")
    response = await agent_service.process_message(
        user_message_dto=schemas.MessageCreate(
            content="Which store had the highest sales in June?",
            brand=None,
            category=None,
            thread_id=1,
        ),
    )
    print(response)


# Test
if __name__ == "__main__":
    asyncio.run(main())
