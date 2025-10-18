"""
Labeling Functions for Scheduling Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class SchedulingKeywordLF(LabelingFunction):
    """Detects scheduling problems by keyword"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects 'schedule' / 'scheduling' keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        if "schedul" in text_lower:  # Catches schedule, scheduling, scheduled
            return self._label(
                label="scheduling",
                confidence=0.90,
                evidence=["Found scheduling keyword"]
            )

        return self._abstain()


class JobShopKeywordLF(LabelingFunction):
    """Detects job shop scheduling"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects job shop keywords and structure"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        # Direct keywords
        job_shop_keywords = [
            "job shop", "job-shop", "jobshop",
            "jobs.*machines.*sequence", "jobs.*machines.*order"
        ]

        evidence = []
        for keyword in job_shop_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"Job shop pattern: '{keyword}'")

        if evidence:
            return self._label(
                label="scheduling.job_shop",
                confidence=1.0,
                evidence=evidence
            )

        return self._abstain()


class FlowShopKeywordLF(LabelingFunction):
    """Detects flow shop scheduling"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects flow shop keywords and structure"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        # Direct keywords
        flow_shop_keywords = [
            "flow shop", "flow-shop", "flowshop",
            "all jobs.*same sequence",
            "all jobs.*same order",
            "same machine sequence"
        ]

        evidence = []
        for keyword in flow_shop_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"Flow shop pattern: '{keyword}'")

        if evidence:
            return self._label(
                label="scheduling.flow_shop",
                confidence=1.0,
                evidence=evidence
            )

        return self._abstain()


class MakespanKeywordLF(LabelingFunction):
    """Detects makespan objective (common in job/flow shop)"""

    def priority(self) -> LFPriority:
        return LFPriority.MEDIUM

    def description(self) -> str:
        return "Detects makespan objective"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        if "makespan" in text_lower:
            # Check for job/machine context
            has_jobs = any(word in text_lower for word in ["job", "task", "operation"])
            has_machines = any(word in text_lower for word in ["machine", "processor", "resource"])

            if has_jobs and has_machines:
                # Likely job shop or flow shop, but can't determine which
                return self._label(
                    label="scheduling.job_shop",
                    confidence=0.80,
                    evidence=["Found 'makespan'", "Jobs and machines context"]
                )

        return self._abstain()


class ShiftRosteringLF(LabelingFunction):
    """Detects shift rostering / employee scheduling"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects shift rostering keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        rostering_keywords = [
            "shift rostering", "shift scheduling",
            "employee.*shift", "staff.*shift",
            "roster", "crew scheduling",
            "nurse scheduling", "driver rostering"
        ]

        # Also check for schedule + shift combination
        has_schedule = "schedul" in text_lower
        has_shift = "shift" in text_lower
        has_employee = any(word in text_lower for word in ["employee", "staff", "worker", "crew"])

        evidence = []
        for keyword in rostering_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"Rostering pattern: '{keyword}'")

        if evidence:
            return self._label(
                label="scheduling.shift_rostering",
                confidence=0.95,
                evidence=evidence
            )

        # Alternative: schedule + shift + employee
        if has_schedule and has_shift and has_employee:
            return self._label(
                label="scheduling.shift_rostering",
                confidence=0.85,
                evidence=["Schedule + shift + employee context"]
            )

        return self._abstain()
