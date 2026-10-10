"""
Query Optimizer - Preprocesses and enhances user questions before agent processing
"""

import re
from typing import Dict, List, Optional, Tuple
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class QueryOptimizer:
    """
    Optimizes user queries by:
    1. Expanding abbreviations
    2. Adding context from business domain
    3. Clarifying ambiguous terms
    4. Normalizing region/metric names
    5. Adding implicit requirements (like YoY comparisons)
    """
    
    # Business domain mappings
    METRIC_ALIASES = {
        "sales": "Net Sales (IND AS)",
        "revenue": "Net Sales (IND AS)",
        "topline": "Net Sales (IND AS)",
        "ebitda": "EBITDA",
        "operating profit": "EBITDA",
        "profit": "Profit After Tax (PAT)",
        "pat": "Profit After Tax (PAT)",
        "pbt": "Profit Before Tax (PBT)",
        "margin": "EBITDA Margin",
        "gross margin": "Gross Contribution %",
        "cogs": "Cost of Goods Sold",
        "a&p": "A&P Spend",
        "marketing spend": "A&P Spend",
        "advertising": "A&P Spend",
        "overheads": "Fixed Overheads",
        "opex": "Operating Expenses",
        "tax": "Taxation",
        "btl": "Below The Line Spend",
        "atl": "Above The Line Spend"
    }
    
    REGION_ALIASES = {
        "indonesia": "Godrej Indonesia",
        "india": "India Standalone",
        "consolidated": "GCPL Consolidated",
        "gcpl": "GCPL Consolidated",
        "africa": "GAUM",
        "latam": "LATAM Pre Hyper",
        "latin america": "LATAM Pre Hyper"
    }
    
    MONTH_ABBREV = {
        "jan": "Jan", "january": "Jan",
        "feb": "Feb", "february": "Feb",
        "mar": "Mar", "march": "Mar",
        "apr": "Apr", "april": "Apr",
        "may": "May",
        "jun": "Jun", "june": "Jun",
        "jul": "Jul", "july": "Jul",
        "aug": "Aug", "august": "Aug",
        "sep": "Sep", "september": "Sep",
        "oct": "Oct", "october": "Oct",
        "nov": "Nov", "november": "Nov",
        "dec": "Dec", "december": "Dec"
    }
    
    def __init__(self, use_llm: bool = True, model_name: str = "gpt-4o-mini"):
        """
        Initialize query optimizer
        
        Args:
            use_llm: Whether to use LLM for advanced optimization (default: True)
            model_name: LLM model to use for optimization (cheaper/faster model recommended)
        """
        self.use_llm = use_llm
        if use_llm:
            self.llm = ChatOpenAI(model=model_name, temperature=1.0)
    
    def optimize(self, query: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, any]:
        """
        Optimize user query through multiple enhancement steps
        
        Args:
            query: Original user query
            conversation_history: Previous conversation messages for context
            
        Returns:
            Dictionary with:
            - optimized_query: Enhanced query string
            - enhancements: List of enhancements applied
            - metadata: Extracted metadata (regions, metrics, periods)
        """
        original_query = query
        enhancements = []
        
        # Step 1: Normalize text
        query = self._normalize_text(query)
        if query != original_query:
            enhancements.append("normalized_text")
        
        # Step 2: Expand abbreviations
        query, abbrev_expanded = self._expand_abbreviations(query)
        if abbrev_expanded:
            enhancements.extend(abbrev_expanded)
        
        # Step 3: Add context from conversation history
        if conversation_history:
            query, context_added = self._add_conversation_context(query, conversation_history)
            if context_added:
                enhancements.append("added_context_from_history")
        
        # Step 4: Extract and normalize entities
        metadata = self._extract_entities(query)
        
        # Step 5: Add implicit requirements based on query pattern
        query, implicit_added = self._add_implicit_requirements(query, metadata)
        if implicit_added:
            enhancements.extend(implicit_added)
        
        # Step 6: LLM-based enhancement (if enabled)
        if self.use_llm:
            query = self._llm_enhance(query, original_query, metadata)
            enhancements.append("llm_enhanced")
        
        return {
            "original_query": original_query,
            "optimized_query": query,
            "enhancements": enhancements,
            "metadata": metadata
        }
    
    def _normalize_text(self, query: str) -> str:
        """Normalize text - lowercase, remove extra spaces, etc."""
        query = query.strip()
        query = re.sub(r'\s+', ' ', query)  # Remove extra spaces
        return query
    
    def _expand_abbreviations(self, query: str) -> Tuple[str, List[str]]:
        """Expand common business abbreviations"""
        expanded = []
        query_lower = query.lower()
        
        # Expand metrics
        for abbrev, full_name in self.METRIC_ALIASES.items():
            if abbrev in query_lower and abbrev != full_name.lower():
                query = re.sub(
                    rf'\b{re.escape(abbrev)}\b',
                    full_name,
                    query,
                    flags=re.IGNORECASE
                )
                expanded.append(f"expanded_{abbrev}_to_{full_name}")
        
        # Expand regions
        for abbrev, full_name in self.REGION_ALIASES.items():
            if abbrev in query_lower and abbrev != full_name.lower():
                query = re.sub(
                    rf'\b{re.escape(abbrev)}\b',
                    full_name,
                    query,
                    flags=re.IGNORECASE
                )
                expanded.append(f"expanded_{abbrev}_to_{full_name}")
        
        # Expand months
        for abbrev, full_name in self.MONTH_ABBREV.items():
            if abbrev in query_lower:
                query = re.sub(
                    rf'\b{re.escape(abbrev)}\b',
                    full_name,
                    query,
                    flags=re.IGNORECASE
                )
        
        return query, expanded
    
    def _add_conversation_context(self, query: str, history: List[Dict]) -> Tuple[str, bool]:
        """Add context from previous conversation if query is ambiguous"""
        # Check if query is a follow-up (e.g., "what about last year?", "show organic too")
        follow_up_indicators = [
            "what about", "show me", "how about", "compare with",
            "last year", "previous", "also", "too", "as well"
        ]
        
        is_followup = any(indicator in query.lower() for indicator in follow_up_indicators)
        
        if is_followup and len(history) > 0:
            # Get last user query for context
            last_query = None
            for msg in reversed(history):
                if msg.get("role") == "user":
                    last_query = msg.get("content")
                    break
            
            if last_query:
                # Extract entities from previous query
                prev_metadata = self._extract_entities(last_query)
                
                # Add context to current query
                context_parts = []
                if prev_metadata.get("regions") and "region" not in query.lower():
                    context_parts.append(f"for {prev_metadata['regions'][0]}")
                if prev_metadata.get("metrics") and "metric" not in query.lower():
                    context_parts.append(f"{prev_metadata['metrics'][0]}")
                
                if context_parts:
                    query = f"{query} {' '.join(context_parts)}"
                    return query, True
        
        return query, False
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract regions, metrics, time periods from query"""
        metadata = {
            "regions": [],
            "metrics": [],
            "periods": [],
            "comparisons": []
        }
        
        query_lower = query.lower()
        
        # Extract regions
        for region in self.REGION_ALIASES.values():
            if region.lower() in query_lower:
                metadata["regions"].append(region)
        
        # Extract metrics
        for metric in self.METRIC_ALIASES.values():
            if metric.lower() in query_lower:
                metadata["metrics"].append(metric)
        
        # Extract time periods
        months = re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', query, re.IGNORECASE)
        years = re.findall(r'\b(20\d{2})\b', query)
        
        if months:
            metadata["periods"].extend([m.capitalize() for m in months])
        if years:
            metadata["periods"].extend(years)
        
        # Detect comparison requests
        comparison_keywords = ["compare", "vs", "versus", "yoy", "mom", "change", "growth", "trend"]
        for keyword in comparison_keywords:
            if keyword in query_lower:
                metadata["comparisons"].append(keyword)
        
        return metadata
    
    def _add_implicit_requirements(self, query: str, metadata: Dict) -> Tuple[str, List[str]]:
        """Add implicit requirements based on query pattern"""
        added = []
        
        # If asking for a single period metric, suggest adding YoY comparison
        if metadata["periods"] and not metadata["comparisons"]:
            if any(word in query.lower() for word in ["what", "show", "give me"]):
                query = f"{query}. Also show year-over-year comparison."
                added.append("added_yoy_comparison")
        
        # If asking about margin/percentage, ensure absolute values are requested
        if any(term in query.lower() for term in ["margin", "percentage", "%", "ratio"]):
            if "absolute" not in query.lower() and "value" not in query.lower():
                query = f"{query}. Include absolute values."
                added.append("added_absolute_values_requirement")
        
        # If asking about multiple regions, suggest ranking
        if len(metadata["regions"]) > 1:
            if "rank" not in query.lower() and "compare" not in query.lower():
                query = f"{query}. Rank by performance."
                added.append("added_ranking")
        
        # If asking about EBITDA/margins, suggest showing components
        if any(term in query.lower() for term in ["ebitda", "margin", "profitability"]):
            if "breakdown" not in query.lower() and "component" not in query.lower():
                query = f"{query}. Show key components."
                added.append("added_components")
        
        return query, added
    
    def _llm_enhance(self, query: str, original_query: str, metadata: Dict) -> str:
        """Use LLM to enhance query with business context"""
        
        prompt = f"""You are optimizing a financial analyst query for GCPL (Godrej Consumer Products).

Original Query: "{original_query}"
Preprocessed Query: "{query}"

Extracted Metadata:
- Regions: {metadata.get('regions', [])}
- Metrics: {metadata.get('metrics', [])}
- Periods: {metadata.get('periods', [])}
- Comparisons: {metadata.get('comparisons', [])}

TASK: Rewrite the query to be more specific and complete for a financial analyst assistant. 

RULES:
1. Keep the core question the same
2. Add clarifying details (e.g., "Net Sales" instead of just "sales")
3. Add standard analytical requirements (e.g., "with YoY comparison")
4. Specify both Reported and Organic if not mentioned
5. Keep it concise - max 2-3 sentences
6. Use proper business terminology

OUTPUT: Return ONLY the optimized query, nothing else.

Optimized Query:"""
        
        try:
            response = self.llm.invoke(prompt)
            enhanced = response.content.strip()
            
            # Validate that enhancement is reasonable (not too long, not completely different)
            if len(enhanced) < len(query) * 3 and len(enhanced) > 10:
                return enhanced
            else:
                return query
        except Exception as e:
            # If LLM fails, return preprocessed query
            return query


# Helper function for easy integration
def optimize_query(
    query: str,
    conversation_history: Optional[List[Dict]] = None,
    use_llm: bool = True
) -> str:
    """
    Quick function to optimize a query
    
    Args:
        query: Original user query
        conversation_history: Previous conversation messages
        use_llm: Whether to use LLM enhancement
        
    Returns:
        Optimized query string
    """
    optimizer = QueryOptimizer(use_llm=use_llm)
    result = optimizer.optimize(query, conversation_history)
    return result["optimized_query"]


# Example usage
if __name__ == "__main__":
    optimizer = QueryOptimizer(use_llm=True)
    
    test_queries = [
        "Give me sales for Indonesia in dec-24",
        "What's the margin?",
        "Compare India and LATAM",
        "Show EBITDA for Q3",
        "How did we perform last month?"
    ]
    
    print("=" * 80)
    print("Query Optimizer Test")
    print("=" * 80)
    
    for query in test_queries:
        result = optimizer.optimize(query)
        print(f"\nOriginal: {result['original_query']}")
        print(f"Optimized: {result['optimized_query']}")
        print(f"Enhancements: {', '.join(result['enhancements'])}")
        print("-" * 80)
