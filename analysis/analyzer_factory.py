# analysis/analyzer_factory.py
from typing import Optional
from .analyzers.base import BaseAnalyzer
from .analyzers.transportation import TransportationAnalyzer
from .analyzers.supply_chain import SupplyChainAnalyzer
from .analyzers.scheduling import SchedulingAnalyzer
from .analyzers.portfolio import PortfolioAnalyzer

class AnalyzerFactory:
    """Factory to get the appropriate analyzer based on problem type"""

    # Registry of available analyzers
    _analyzers = {
        "TRANSPORTATION": TransportationAnalyzer,
        "SUPPLY_CHAIN": SupplyChainAnalyzer,
        "SCHEDULING": SchedulingAnalyzer,
        "PORTFOLIO": PortfolioAnalyzer,
    }

    @classmethod
    def get_analyzer(cls, problem_type: str, llm_client=None) -> Optional[BaseAnalyzer]:
        """
        Get the appropriate analyzer for a problem type

        Args:
            problem_type: Type like "TRANSPORTATION", "SUPPLY_CHAIN", etc.
            llm_client: LLM client for natural language understanding

        Returns:
            Analyzer instance or None if problem type not supported
        """
        analyzer_class = cls._analyzers.get(problem_type.upper())

        if analyzer_class:
            return analyzer_class(llm_client)

        return None

    @classmethod
    def get_supported_problem_types(cls) -> list:
        """Return list of supported problem types"""
        return list(cls._analyzers.keys())

    @classmethod
    def register_analyzer(cls, problem_type: str, analyzer_class: type):
        """
        Register a new analyzer for a problem type

        Args:
            problem_type: Problem type string
            analyzer_class: Analyzer class that extends BaseAnalyzer
        """
        if not issubclass(analyzer_class, BaseAnalyzer):
            raise ValueError("Analyzer class must extend BaseAnalyzer")

        cls._analyzers[problem_type.upper()] = analyzer_class