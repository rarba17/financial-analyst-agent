"""
Standalone GCPL Financial Intelligence Agent - WITH SPECIALIZED TOOLS
Combines SQL generation, execution, and business analysis with 5 specialized tools
Updated to support WebSocket streaming via ai_message_id
"""

import os
import json
import sqlite3
from typing import Optional, Dict, List, Any
from datetime import date
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# Import specialized tools from sibling tools directory
import sys
from pathlib import Path
# Add parent directory to path to access tools module
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import (
    query_basic_metrics,
    analyze_time_series,
    find_rankings_extrema,
    compare_regions,
    analyze_drivers
)

load_dotenv()


class GCPLFinancialAgent:
    """
    Standalone agent for GCPL financial data analysis with 5 specialized tools
    Supports WebSocket streaming via ai_message_id
    """
    
    def __init__(
        self,
        ai_message_id: Optional[str] = None,  
        db_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        sql_prompt_path: Optional[str] = None,
        business_prompt_path: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        enable_query_optimization: bool = False,
    ):
        
        self.ai_message_id = ai_message_id
        
        # Load from environment variables with fallbacks
        self.db_path = db_path or os.getenv("DATABASE_PATH", "flattened.db")
        self.metadata_path = metadata_path or os.getenv("METADATA_PATH", "gcpl_finpac_metadata_v3.json")
        self.sql_prompt_path = sql_prompt_path or os.getenv("SQL_PROMPT_PATH", "godrej.md")
        self.business_prompt_path = business_prompt_path or os.getenv("BUSINESS_PROMPT_PATH", "1.md")
        
        model_name = model_name or os.getenv("LLM_MODEL", "gpt-4o")
        temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.0"))
        
        self.metadata = self._load_metadata()
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=True
        )
        self.conversation_history: List[Dict[str, str]] = []
        
        # Query optimizer
        self.enable_query_optimization = enable_query_optimization
        if enable_query_optimization:
            # Import here to avoid circular dependency
            from query_optimizer import QueryOptimizer
            self.query_optimizer = QueryOptimizer(use_llm=True, model_name="gpt-4o-mini")
        
    def _load_metadata(self) -> dict:
        """Load database metadata from JSON file"""
        with open(self.metadata_path, 'r') as f:
            return json.load(f)
    
    def _get_db_connection(self):
        """Create SQLite database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _load_business_analyst_prompt(self) -> str:
        """Load business analyst system prompt from configured path"""
        with open(self.business_prompt_path, 'r') as f:
            return f.read()
    
    def _create_agent_prompt(self) -> ChatPromptTemplate:
        """Create the agent prompt template with business analyst instructions"""
        business_prompt = self._load_business_analyst_prompt()
        
        system_message = f"""You are a financial analyst assistant for GCPL (Godrej Consumer Products Limited).

{business_prompt}

AVAILABLE TOOLS:
You have access to 5 specialized tools:

1. **query_basic_metrics**: For single-value retrieval (simple queries)
   - Use when: User asks for one metric, one region, one period
   - Example: "What was India's Net Sales in December 2024?"

2. **analyze_time_series**: For MoM changes, trends, rolling averages
   - Use when: User asks about changes over time, trends, rolling averages
   - Example: "What's the MoM change in EBITDA from Feb to Mar 2025?"

3. **find_rankings_extrema**: For finding peaks, valleys, best/worst months
   - Use when: User asks "which month had highest/lowest" or "peak" or "minimum"
   - Example: "Which month shows peak EBITDA for India?"

4. **compare_regions**: For cross-region comparisons and rankings
   - Use when: User wants to compare multiple regions for same period
   - Example: "Rank India, Indonesia, and Africa by Net Sales in March 2025"

5. **analyze_drivers**: For complex analysis (waterfalls, driver attribution, mix)
   - Use when: User asks about "drivers", "decomposition", "waterfall", "mix analysis"
   - Example: "What are the top drivers of EBITDA change?"

WORKFLOW:
1. Understand the user's question (refer to chat history for context)
2. SELECT THE MOST APPROPRIATE TOOL based on query type
3. Call the tool with correct parameters
4. Analyze the results and provide insights following the business analyst guidelines
5. Format response in clear, professional Markdown with tables where appropriate
6. Always include relevant comparisons (YoY, MoM, splits, etc.)
1
CRITICAL:
- Choose the RIGHT tool for the query type
- For simple queries → use query_basic_metrics
- For time-based analysis → use analyze_time_series
- For finding extrema → use find_rankings_extrema
- For regional comparison → use compare_regions
- For complex decomposition → use analyze_drivers

REMEMBER:
- Always fetch standard siblings when relevant (e.g., Total + Domestic + Exports)
- Include YoY comparisons when analyzing periods
- Show both absolute values and percentages for margins/ratios
- Calculate derived metrics (like Effective Tax Rate) automatically
- Cite data sources clearly (period, region, metric)
- End with contextual follow-up suggestions
- Never expose tool names or technical implementation to users
"""
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
    
    def _build_agent(self) -> AgentExecutor:
        """Build the LangChain agent with all 5 specialized tools"""
        
        # All 5 specialized tools
        tools = [
            query_basic_metrics,
            analyze_time_series,
            find_rankings_extrema,
            compare_regions,
            analyze_drivers
        ]
        
        # Create prompt
        prompt = self._create_agent_prompt()
        
        # Create agent
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=tools,
            prompt=prompt
        )
        
        # Create executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=5,
            early_stopping_method="generate"
        )
        
        return agent_executor
    
    async def run(self, query: str, history_context: Optional[List] = None, stream: bool = False) -> str:
        """
        Run the agent with a user query
        
        Args:
            query: User's natural language question
            history_context: Optional conversation history (for compatibility with agent_service)
            stream: Whether to stream the response (default: False)
            
        Returns:
            Agent's response as string
        """
        # ✅ ADDED: Support for WebSocket streaming via chat_status_service
        if self.ai_message_id:
            try:
                from services.chat_status_service import chat_status_service
                await chat_status_service.send_status(
                    self.ai_message_id, 
                    "Analyzing your financial query..."
                )
            except Exception as e:
                print(f"[GCPLFinancialAgent] Could not send status: {e}")
        
        # Use provided history_context if available, otherwise use internal history
        if history_context is not None:
            # Convert history_context format to internal format
            self.conversation_history = []
            for msg in history_context:
                self.conversation_history.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Optimize query if enabled
        optimized_query = query
        optimization_result = None
        if self.enable_query_optimization:
            optimization_result = self.query_optimizer.optimize(
                query, 
                self.conversation_history
            )
            optimized_query = optimization_result["optimized_query"]
            
            # Log optimization for debugging
            if optimized_query != query:
                print(f"🔍 Query Optimization Applied:")
                print(f"   Original: {query}")
                print(f"   Optimized: {optimized_query}")
                print(f"   Enhancements: {', '.join(optimization_result['enhancements'])}")
                print()
        
        agent_executor = self._build_agent()
        
        # Convert conversation history to LangChain messages
        chat_history = []
        for msg in self.conversation_history:
            if msg["role"] == "user":
                chat_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                chat_history.append(AIMessage(content=msg["content"]))
        
        # Prepare input
        agent_input = {
            "input": optimized_query,
            "chat_history": chat_history
        }
        
        # ✅ ADDED: Stream to WebSocket if ai_message_id is provided
        if self.ai_message_id and stream:
            try:
                from services.chat_status_service import chat_status_service
                output = ""
                for chunk in agent_executor.stream(agent_input):
                    if "output" in chunk:
                        content = chunk["output"]
                        await chat_status_service.stream_response(self.ai_message_id, content)
                        output += content
                result = output
            except Exception as e:
                print(f"[GCPLFinancialAgent] Streaming error: {e}")
                # Fallback to non-streaming
                result = agent_executor.invoke(agent_input)
                result = result.get("output", "")
        elif stream:
            # Console streaming (no WebSocket)
            output = ""
            for chunk in agent_executor.stream(agent_input):
                if "output" in chunk:
                    content = chunk["output"]
                    print(content, end="", flush=True)
                    output += content
            print()  # New line after streaming
            result = output
        else:
            # Non-streaming mode
            result = agent_executor.invoke(agent_input)
            result = result.get("output", "")
        
        # Update conversation history with ORIGINAL query (not optimized)
        original_query = optimization_result["original_query"] if optimization_result else query
        self.conversation_history.append({"role": "user", "content": original_query})
        self.conversation_history.append({"role": "assistant", "content": result})
        
        # ✅ ADDED: Send completion status
        if self.ai_message_id:
            try:
                from services.chat_status_service import chat_status_service
                await chat_status_service.send_status(self.ai_message_id, "stream_completed")
            except Exception as e:
                print(f"[GCPLFinancialAgent] Could not send completion status: {e}")
        
        return result
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history


def main():
    """Example usage"""
    # Initialize agent
    agent = GCPLFinancialAgent(
        db_path="flattened.db",
        metadata_path="gcpl_finpac_metadata_v3.json",
        model_name="gpt-4o"
    )
    
    # Example queries for each tool
    queries = [
        # Tool 1: Basic Metrics
        "What was India's Net Sales in December 2024?",
        
        # Tool 2: Time Series
        "What's the MoM change in EBITDA from February to March 2025 for India?",
        
        # Tool 3: Rankings
        "Which month between Oct 2024 and Mar 2025 had the peak EBITDA for India?",
        
        # Tool 4: Comparison
        "Rank India, Indonesia, and GAUM by Net Sales in March 2025",
        
        # Tool 5: Driver Analysis
        "What are the top 3 drivers of EBITDA change for India from Oct 2024 to Mar 2025?"
    ]
    
    print("=" * 80)
    print("GCPL Financial Intelligence Agent - With Specialized Tools")
    print("=" * 80)
    print()
    
    # Run first example query
    query = queries[0]
    print(f"Query: {query}")
    print("-" * 80)
    
    import asyncio
    response = asyncio.run(agent.run(query, stream=True))
    
    print("\n" + "=" * 80)
    print()


if __name__ == "__main__":
    main()