"""
Interactive CLI for CCPL Financial Intelligence Agent
Provides a user-friendly command-line interface for financial analysis
"""

import os
import sys
from typing import Optional
from .standalone_agent import GCPLFinancialAgent


class InteractiveCLI:
    """Interactive command-line interface for the CCPL agent"""

    def __init__(self):
        self.agent: Optional[GCPLFinancialAgent] = None
        self.running = False

    def initialize_agent(self):
        """Initialize the CCPL agent"""
        print("🔧 Initializing CCPL Financial Intelligence Agent...")

        # Load environment
        from dotenv import load_dotenv
        load_dotenv()

        # Check for required files (using env paths)
        required_files = {
            os.getenv("DATABASE_PATH", "flattened.db"): "Database",
            os.getenv("METADATA_PATH", "CCPL_finpac_metadata_v3.json"): "Metadata",
            os.getenv("SQL_PROMPT_PATH", "godrej.md"): "SQL Prompt",
            os.getenv("BUSINESS_PROMPT_PATH", "1.md"): "Business Prompt"
        }

        missing_files = []
        for filepath, name in required_files.items():
            if not os.path.exists(filepath):
                missing_files.append(f"{name} ({filepath})")

        if missing_files:
            print(f"❌ Error: Missing required files:")
            for missing in missing_files:
                print(f"   - {missing}")
            print("\n💡 Configure file paths in .env file:")
            print("   DATABASE_PATH=/path/to/flattened.db")
            print("   METADATA_PATH=/path/to/metadata.json")
            print("   SQL_PROMPT_PATH=/path/to/godrej.md")
            print("   BUSINESS_PROMPT_PATH=/path/to/1.md")
            return False

        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ Error: OPENAI_API_KEY environment variable not set")
            return False

        try:
            self.agent = GCPLFinancialAgent()  # Uses env variables automatically
            print("✅ Agent initialized successfully!\n")
            return True
        except Exception as e:
            print(f"❌ Error initializing agent: {str(e)}")
            return False

    def print_banner(self):
        """Print welcome banner"""
        banner = """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║        CCPL Financial Intelligence Agent                       ║
║        Standalone Version - Interactive CLI                    ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

Welcome! I'm your financial analyst assistant for CCPL data.
Ask me anything about revenue, profitability, margins, or trends.

Type 'help' for available commands or start asking questions!
"""
        print(banner)

    def print_help(self):
        """Print help information"""
        help_text = """
Available Commands:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Analysis Commands:
  • Just type your question naturally (e.g., "Show me India sales for Dec-24")
  • The agent will fetch data and provide insights

🔧 Utility Commands:
  • help              - Show this help message
  • examples          - Show example queries
  • history           - View conversation history
  • clear             - Clear conversation history
  • exit / quit       - Exit the application

💡 Example Questions:
  • "Give me Net Sales for Indonesia in Dec-24"
  • "What was BTL spend in Argentina during Dec-24?"
  • "How much Operational EBITDA did CCPL Consolidated book in Dec-24?"
  • "Compare EBITDA margins across all regions for Dec-24"
  • "Show me India sales performance for Q2 2024"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        print(help_text)

    def print_examples(self):
        """Print example queries"""
        examples = """
Example Queries:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Revenue & Sales:
  • "Show me total sales for India in Q3 2024"
  • "What was Net Sales for Indonesia in December 2024?"
  • "Compare revenue across all regions for Dec-24"
  • "Give me Gross Sales breakdown (Domestic + Export) for LATAM"

Profitability:
  • "What's the EBITDA margin for India in Dec-24?"
  • "Show me PAT for CCPL Consolidated in Q2"
  • "How did Gross Contribution perform YoY for Indonesia?"

Costs & Expenses:
  • "What was the BTL spend in Argentina during Dec-24?"
  • "Show me COGS as percentage of Net Sales for India"
  • "What are the Fixed Overheads for GAUM cluster?"
  • "Give me A&P spend breakdown for all regions"

Comparisons & Trends:
  • "Compare EBITDA margins across all regions"
  • "Show YoY growth in Net Sales for India"
  • "What's the month-over-month change in profitability?"

Multi-metric Analysis:
  • "Give me complete P&L summary for Indonesia in Dec-24"
  • "Analyze profitability drivers for India in Q3"
  • "Show me margin trends (Gross, EBITDA, Net) for LATAM"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        print(examples)

    def print_history(self):
        """Print conversation history"""
        if not self.agent or not self.agent.get_history():
            print("📭 No conversation history yet. Start asking questions!\n")
            return

        print("\n📜 Conversation History:")
        print("━" * 70)

        for i, msg in enumerate(self.agent.get_history(), 1):
            role_icon = "🧑" if msg["role"] == "user" else "🤖"
            role_label = "You" if msg["role"] == "user" else "Agent"

            print(f"\n{role_icon} {role_label} (Message {i}):")
            print(msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"])

        print("\n" + "━" * 70 + "\n")

    def clear_history(self):
        """Clear conversation history"""
        if self.agent:
            self.agent.clear_history()
            print("✨ Conversation history cleared!\n")
        else:
            print("⚠️  No agent initialized.\n")

    def process_query(self, query: str):
        """Process user query"""
        if not self.agent:
            print("❌ Agent not initialized. Please restart the application.\n")
            return

        print("\n🤔 Analyzing your query...\n")
        print("━" * 70)

        try:
            # Use asyncio to run the async method
            import asyncio
            response = asyncio.run(self.agent.run(query, stream=True))
            print("\n" + "━" * 70 + "\n")
        except Exception as e:
            print(f"\n❌ Error processing query: {str(e)}\n")

    def run(self):
        """Main CLI loop"""
        if not self.initialize_agent():
            return

        self.print_banner()
        self.running = True

        while self.running:
            try:
                # Get user input
                user_input = input("💬 Your question: ").strip()

                if not user_input:
                    continue

                # Parse commands
                command = user_input.lower()

                if command in ["exit", "quit", "q"]:
                    print("\n👋 Thank you for using CCPL Financial Intelligence Agent. Goodbye!\n")
                    self.running = False
                    break

                elif command == "help":
                    self.print_help()

                elif command == "examples":
                    self.print_examples()

                elif command == "history":
                    self.print_history()

                elif command == "clear":
                    self.clear_history()

                else:
                    # Process as a query
                    self.process_query(user_input)

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user. Type 'exit' to quit.\n")
            except Exception as e:
                print(f"\n❌ Unexpected error: {str(e)}\n")


def main():
    """Entry point"""
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()