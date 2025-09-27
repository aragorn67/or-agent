# conversation/agent.py
from typing import Dict, Any
from agent.core import OptimizationAgent
from conversation.memory import conversation_memory

class ConversationalAgent(OptimizationAgent):
    """Agent with conversation capabilities and context awareness"""

    def __init__(self, llm_client):
        super().__init__(llm_client)
        self.memory = conversation_memory

    def process_message(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """Process a conversational message with context awareness"""

        print(f"🐛 DEBUG: Processing message: '{user_message}'")
        print(f"🐛 DEBUG: Session ID: {session_id}")

        # Get conversation context
        context = self.memory.get_context(session_id)
        print(f"🐛 DEBUG: Context keys: {list(context.keys()) if context else 'None'}")

        # Add user message to memory
        self.memory.add_message(session_id, "user", user_message)

        try:
            # Only check for follow-up if there's a previous solution
            last_solution = context.get("last_solution")
            print(f"🐛 DEBUG: Has last_solution: {last_solution is not None}")

            if last_solution:
                print(f"🐛 DEBUG: Last solution problem type: {last_solution.get('problem_type', 'Unknown')}")

                # Check if this is a completely new problem (different entities)
                is_new_problem = self._detect_new_problem(user_message, context)
                print(f"🐛 DEBUG: Is new problem: {is_new_problem}")

                if is_new_problem:
                    print(f"🐛 DEBUG: Handling as NEW problem (clearing context)")
                    # Clear previous context for new problem
                    self.memory.clear_solution_context(session_id)
                    return self._handle_new_problem(session_id, user_message)

                # Detect if this is a follow-up request
                print(f"🐛 DEBUG: Checking follow-up intent...")
                follow_up_info = self.llm.detect_follow_up_intent(user_message, context)
                print(f"🐛 DEBUG: Follow-up info: {follow_up_info}")

                if follow_up_info.get("is_follow_up", False):
                    print(f"🐛 DEBUG: Handling as FOLLOW-UP")
                    return self._handle_follow_up(session_id, user_message, context, follow_up_info)
                else:
                    print(f"🐛 DEBUG: Follow-up detection failed, treating as new problem")

            # Handle as new problem if no previous solution or not a follow-up
            return self._handle_new_problem(session_id, user_message)

        except Exception as e:
            error_response = {
                "success": False,
                "error": f"Conversation error: {str(e)}",
                "is_follow_up": False
            }

            # Add error response to memory
            self.memory.add_message(session_id, "assistant", f"Error: {str(e)}", error_response)
            return error_response

    def _handle_follow_up(self, session_id: str, user_message: str, context: Dict, follow_up_info: Dict) -> Dict[str, Any]:
        """Handle follow-up requests that reference previous solutions"""

        follow_up_type = follow_up_info.get("follow_up_type", "analysis")
        analysis_types = follow_up_info.get("analysis_requested", [])

        last_solution = context.get("last_solution")
        last_params = context.get("last_params")

        if not last_solution:
            response = {
                "success": False,
                "error": "No previous solution found to analyze",
                "is_follow_up": True,
                "suggestion": "Please first solve an optimization problem, then I can help with follow-up analysis."
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

        if follow_up_type == "modification":
            return self._handle_modification(session_id, user_message, last_params)

        elif follow_up_type == "analysis":
            return self._handle_analysis_request(session_id, user_message, last_solution, last_params, analysis_types)

        elif follow_up_type == "question":
            return self._handle_solution_question(session_id, user_message, last_solution)

        else:
            # Default to explanation
            explanation = self.llm.explain_solution(last_solution.get("solution", {}), last_solution.get("problem_type", ""))

            response = {
                "success": True,
                "content": explanation,
                "is_follow_up": True,
                "follow_up_type": "explanation"
            }

            self.memory.add_message(session_id, "assistant", explanation, response)
            return response

    def _handle_modification(self, session_id: str, user_message: str, last_params: Dict) -> Dict[str, Any]:
        """Handle parameter modification requests"""

        if not last_params:
            response = {
                "success": False,
                "error": "No previous parameters found to modify",
                "is_follow_up": True
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

        # Extract what the user wants to modify
        modification_info = self.llm.extract_modification_parameters(user_message, last_params)

        if modification_info.get("confidence", 0) < 0.3:
            response = {
                "success": False,
                "error": "Could not understand what you want to modify. Please be more specific.",
                "is_follow_up": True,
                "suggestion": "Try: 'Increase Seattle capacity to 500' or 'Double the freight costs'"
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

        # Apply modifications
        modified_params = self._apply_modifications(last_params.copy(), modification_info["modifications"])

        # Solve with modified parameters
        agent_response = f"🔄 Applying changes: {modification_info['change_description']}\n\nRe-solving optimization..."

        try:
            # Use the parent class method to solve
            result = self.solve_natural_language(f"Previous problem with modifications: {modification_info['change_description']}")

            # Override with modified parameters
            if result.get("success"):
                solver = self._get_solver_for_params(modified_params)
                if solver:
                    modified_solution = solver.solve(modified_params)
                    result["solution"] = modified_solution
                    result["extracted_params"] = modified_params
                    result["modification_applied"] = modification_info

            result["is_follow_up"] = True
            result["follow_up_type"] = "modification"

            self.memory.add_message(session_id, "assistant", agent_response, result)
            return result

        except Exception as e:
            response = {
                "success": False,
                "error": f"Error applying modifications: {str(e)}",
                "is_follow_up": True
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

    def _handle_analysis_request(self, session_id: str, user_message: str, last_solution: Dict, last_params: Dict, analysis_types: list) -> Dict[str, Any]:
        """Handle analysis requests like sensitivity, Pareto, etc."""

        if not last_params or not last_solution:
            response = {
                "success": False,
                "error": "No previous solution found for analysis",
                "is_follow_up": True
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

        try:
            # FALLBACK: Check if this should actually be a question (misclassified)
            message_lower = user_message.lower()
            question_indicators = [
                "what insights", "give me insights", "tell me about",
                "what can you tell me", "what information", "explain this",
                "what can you do", "what are we trying", "what function",
                "what limitations", "what restrictions", "what constraints",
                "what's the goal", "what is the objective", "what are we optimizing",
                "how many", "what types of analyses", "analysis options"
            ]

            if any(phrase in message_lower for phrase in question_indicators):
                # This should be handled as a question, not analysis
                return self._handle_solution_question(session_id, user_message, last_solution)

            # Check if this is a sensitivity analysis request
            if any(word in user_message.lower() for word in ["affect", "impact", "effect", "sensitivity"]):
                return self._perform_sensitivity_analysis(session_id, user_message, last_solution, last_params)

            # Check if user wants plots/visualizations
            wants_plots = any(word in user_message.lower() for word in
                             ["plot", "chart", "graph", "visual", "diagram", "show", "display"])

            # Generate meaningful analysis content
            analysis_content = self._generate_analysis_content(user_message, last_solution, last_params)

            response = {
                "success": True,
                "content": analysis_content,
                "is_follow_up": True,
                "follow_up_type": "analysis"
            }

            # If user wants plots, add them to the response
            if wants_plots or "relationship" in user_message.lower() or "cost" in user_message.lower():
                # Use the cached solution from the previous request
                plot_result = {"solution": last_solution.get("solution", {})}
                response = self._add_plots_to_result(response, plot_result)
                response["content"] += "\n\n🎯 Visualizations showing the relationships:"

            self.memory.add_message(session_id, "assistant", response["content"], response)
            return response

        except Exception as e:
            response = {
                "success": False,
                "error": f"Analysis error: {str(e)}",
                "is_follow_up": True
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

    def _handle_solution_question(self, session_id: str, user_message: str, last_solution: Dict) -> Dict[str, Any]:
        """Handle questions about the existing solution using LLM categorization"""

        # Use LLM to categorize the question and determine the best response type
        question_type = self._categorize_question(user_message, last_solution)

        if question_type == "capabilities":
            return self._provide_capabilities_info(session_id, last_solution)
        elif question_type == "objective":
            return self._provide_objective_info(session_id, last_solution)
        elif question_type == "dimensions":
            return self._provide_problem_size_info(session_id, last_solution)
        elif question_type == "constraints":
            return self._provide_constraints_info(session_id, last_solution)
        else:
            # For general questions, use LLM to provide a custom answer
            return self._provide_general_answer(session_id, user_message, last_solution)

    def _categorize_question(self, user_message: str, last_solution: Dict) -> str:
        """Use LLM to intelligently categorize the user's question"""

        problem_type = last_solution.get('problem_type', 'optimization')

        prompt = f"""
Categorize this user question about a {problem_type.lower()} optimization problem:

User question: "{user_message}"

Choose the BEST category from these options:

1. "capabilities" - Questions about what analyses can be performed
   Examples: "what types of analyses?", "what can you do?", "analysis options"

2. "objective" - Questions about the optimization goal/objective function
   Examples: "what are we minimizing?", "what's the goal?", "objective function"

3. "dimensions" - Questions about problem size/scale
   Examples: "how many variables?", "how many locations?", "problem size"

4. "constraints" - Questions about rules/limitations/restrictions
   Examples: "what constraints?", "what rules?", "limitations", "restrictions"

5. "general" - Any other question about the problem or solution
   Examples: "explain the solution", "what does this mean?", specific solution details

Return ONLY the category name (capabilities, objective, dimensions, constraints, or general).
"""

        try:
            response = self.llm._chat("", prompt, json_mode=False).strip().lower()

            # Validate response
            valid_categories = ["capabilities", "objective", "dimensions", "constraints", "general"]
            if response in valid_categories:
                return response
            else:
                # If LLM gives invalid response, fall back to general
                return "general"

        except Exception:
            # If LLM fails, fall back to general
            return "general"

    def _provide_general_answer(self, session_id: str, user_message: str, last_solution: Dict) -> Dict[str, Any]:
        """Provide a general answer using LLM"""

        context = self.memory.get_context(session_id)
        last_params = context.get("last_params", {})

        prompt = f"""
Answer this question about an optimization problem:

Question: "{user_message}"

Problem type: {last_solution.get('problem_type', 'Unknown')}
Solution data: {last_solution.get('solution', {})}
Problem parameters: {last_params}

Provide a clear, helpful answer. Focus on being informative and concise.
If the question is about specific numbers or details, extract them from the data provided.
"""

        try:
            explanation = self.llm._chat("", prompt, json_mode=False)

            response = {
                "success": True,
                "content": explanation,
                "is_follow_up": True,
                "follow_up_type": "question"
            }

            self.memory.add_message(session_id, "assistant", explanation, response)
            return response

        except Exception as e:
            response = {
                "success": False,
                "error": f"Could not answer question: {str(e)}",
                "is_follow_up": True
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response

    def _handle_new_problem(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """Handle new optimization problems"""

        print(f"🐛 DEBUG: _handle_new_problem called with: '{user_message}'")

        # Use parent class method
        result = self.solve_natural_language(user_message)
        print(f"🐛 DEBUG: solve_natural_language result success: {result.get('success', False)}")
        if not result.get('success'):
            print(f"🐛 DEBUG: Error details: {result.get('error', 'Unknown')}")
        result["is_follow_up"] = False

        # Check if user wants plots/visualizations
        wants_plots = any(word in user_message.lower() for word in
                         ["plot", "chart", "graph", "visual", "diagram", "show", "display"])

        if result.get("success") and wants_plots:
            result = self._add_plots_to_result(result)

        # Add to memory with detailed error handling
        if result.get("success"):
            content = "✅ Solution found!"
        else:
            error_msg = result.get('error', 'Unknown error')
            details = result.get('details', [])
            suggestion = result.get('suggestion', '')

            content = f"❌ **{error_msg}**\n\n"

            if details:
                content += "**Details:**\n"
                for detail in details:
                    content += f"• {detail}\n"
                content += "\n"

            if suggestion:
                content += f"**💡 Suggestion:** {suggestion}\n"

        self.memory.add_message(session_id, "assistant", content, result)

        return result

    def _perform_sensitivity_analysis(self, session_id: str, user_message: str, last_solution: Dict, last_params: Dict) -> Dict[str, Any]:
        """Perform actual sensitivity analysis and generate plot"""
        try:
            # Import the analysis engine and factory
            from analysis.engine import AnalysisEngine
            from analysis.analyzer_factory import AnalyzerFactory

            analysis_engine = AnalysisEngine()

            # Get the appropriate analyzer for this problem type
            problem_type = last_solution.get("problem_type", "TRANSPORTATION")
            analyzer = AnalyzerFactory.get_analyzer(problem_type, self.llm)

            if not analyzer:
                response = {
                    "success": False,
                    "error": f"No analyzer available for problem type: {problem_type}",
                    "is_follow_up": True
                }
                self.memory.add_message(session_id, "assistant", response["error"], response)
                return response

            # Use the analyzer to extract the variable from natural language
            variable_name, original_value = analyzer.extract_variable_from_message(user_message, last_params)

            if not variable_name or not original_value:
                response = {
                    "success": False,
                    "error": "Could not understand which variable to analyze",
                    "is_follow_up": True,
                    "suggestion": "Try being more specific, like: 'How does capacity affect cost?' or 'What if we change the distance?'"
                }
                self.memory.add_message(session_id, "assistant", response["error"], response)
                return response

            # Create range (50% to 150% of original)
            range_min = original_value * 0.5
            range_max = original_value * 1.5

            # Perform sensitivity analysis
            analysis_result = analysis_engine.run_sensitivity_analysis(
                last_params, variable_name, (range_min, range_max), steps=20
            )

            # Generate plot
            plot_b64 = analysis_engine.create_sensitivity_plot(analysis_result)

            # Create response with plot using analyzer's description
            variable_description = analyzer.get_variable_description(variable_name, original_value)

            content = f"📊 **Sensitivity Analysis: {variable_name}**\n\n"
            content += f"{variable_description}\n\n"
            content += f"**Analysis Parameters:**\n"
            content += f"• Range tested: {range_min:.1f} to {range_max:.1f}\n"
            content += f"• Analysis points: 20 scenarios\n\n"
            content += "See the plot below showing how this variable affects the total cost:"

            response = {
                "success": True,
                "content": content,
                "is_follow_up": True,
                "follow_up_type": "sensitivity_analysis",
                "analysis": [{
                    "type": "sensitivity_analysis",
                    "description": f"Sensitivity Analysis: {variable_name}",
                    "variable": variable_name,
                    "data": analysis_result,
                    "plot_base64": plot_b64
                }]
            }

            # Cache the plot for API serving
            import api
            api._cached_sensitivity_plot = plot_b64
            response["plot_urls"] = {
                "sensitivity_plot": "/plots/sensitivity.png"
            }
            response["has_plots"] = True

            self.memory.add_message(session_id, "assistant", content, response)
            return response

        except Exception as e:
            response = {
                "success": False,
                "error": f"Sensitivity analysis failed: {str(e)}",
                "is_follow_up": True,
                "suggestion": "Please ensure your previous optimization was successful before requesting analysis."
            }
            self.memory.add_message(session_id, "assistant", response["error"], response)
            return response


    def _apply_modifications(self, params: Dict, modifications: Dict) -> Dict:
        """Apply parameter modifications"""

        if "capacity" in modifications:
            for plant, new_capacity in modifications["capacity"].items():
                if "capacity" in params and plant in params["capacity"]:
                    params["capacity"][plant] = new_capacity

        if "demand" in modifications:
            for market, new_demand in modifications["demand"].items():
                if "demand" in params and market in params["demand"]:
                    params["demand"][market] = new_demand

        if "freight" in modifications:
            params["freight"] = modifications["freight"]

        return params

    def _get_solver_for_params(self, params: Dict):
        """Get appropriate solver for parameters"""
        try:
            from solvers import get_solver
            return get_solver("TRANSPORTATION")
        except:
            return None

    def _add_plots_to_result(self, result: Dict, solution_data: Dict = None) -> Dict:
        """Add plot URLs to result for visualization"""
        try:
            # Import at module level to access the global variable
            import api

            # Use provided solution_data or extract from result
            solution_to_cache = solution_data.get("solution") if solution_data else result.get("solution")

            if solution_to_cache:
                # Cache the solution for the plotting endpoints
                api._cached_solution = solution_to_cache

                # Add plot URLs to the result
                result["plot_urls"] = {
                    "shipments_by_plant": "/plots/shipments_by_plant.png",
                    "shipments_matrix": "/plots/shipments_matrix.png"
                }

                result["has_plots"] = True
            else:
                result["plot_error"] = "No solution data available for plotting"

            return result

        except Exception as e:
            # If plot generation fails, don't break the main result
            result["plot_error"] = f"Could not generate plots: {str(e)}"
            return result

    def _generate_analysis_content(self, user_message: str, last_solution: Dict, last_params: Dict) -> str:
        """Generate meaningful analysis content based on user question"""
        try:
            solution = last_solution.get("solution", {})

            if "relationship" in user_message.lower() and "cost" in user_message.lower():
                # Analyze cost relationships
                flows = solution.get("flows", [])
                total_cost = solution.get("objective_thousand_usd", 0)

                # Calculate number of active routes
                active_routes = len([f for f in flows if f.get("value", 0) > 0.01])

                content = f"📊 **Cost Relationship Analysis**\n\n"
                content += f"**Current Solution:**\n"
                content += f"• Total shipping cost: ${total_cost:.2f}k\n"
                content += f"• Active shipping routes: {active_routes}\n"
                content += f"• Average cost per active route: ${total_cost/max(active_routes,1):.2f}k\n\n"

                content += f"**Key Insights:**\n"
                content += f"• More customers generally increase total cost due to distribution complexity\n"
                content += f"• However, economies of scale can reduce per-unit costs\n"
                content += f"• Distance is the primary cost driver at $90 per case per 1000 miles\n"

                return content

            elif "sensitivity" in user_message.lower() or "affect" in user_message.lower():
                content = f"📊 **Sensitivity Analysis**\n\n"
                content += f"This solution is sensitive to:\n"
                content += f"• **Freight rates**: Currently $90/case/1000mi\n"
                content += f"• **Capacity constraints**: Seattle (350), San Diego (600)\n"
                content += f"• **Demand changes**: Any increase would require capacity expansion\n"
                return content

            else:
                # General analysis
                content = f"📊 **Analysis Results**\n\n"
                content += f"For more specific analysis, try asking:\n"
                content += f"• 'What is the relationship between customers and cost?'\n"
                content += f"• 'How does changing capacity affect the solution?'\n"
                content += f"• 'Show me the trade-offs between cost and service'\n"
                return content

        except Exception as e:
            return f"📊 **Analysis Error**: {str(e)}"

    def _detect_new_problem(self, user_message: str, context: Dict) -> bool:
        """Detect if user is describing a completely new problem vs modifying existing one"""
        try:
            # Check if user is specifying new entities (factories, customers, etc.)
            last_params = context.get("last_params", {})

            # Keywords that indicate a completely new problem setup
            new_problem_indicators = [
                "i have", "i need to", "solve", "optimize", "minimize", "maximize",
                "factories", "plants", "customers", "markets", "warehouses"
            ]

            message_lower = user_message.lower()
            has_new_problem_keywords = any(indicator in message_lower for indicator in new_problem_indicators)

            if not has_new_problem_keywords:
                return False

            # Extract entity names from current message
            import re

            # Look for factory/plant names (after "factories", "plants", etc.)
            factory_patterns = [
                r'factories?\s*\([^)]*?([A-Za-z][A-Za-z0-9\s\-_]*?):\s*\d+',
                r'plants?\s*\([^)]*?([A-Za-z][A-Za-z0-9\s\-_]*?):\s*\d+',
                r'warehouses?\s*\([^)]*?([A-Za-z][A-Za-z0-9\s\-_]*?):\s*\d+'
            ]

            current_factories = set()
            for pattern in factory_patterns:
                matches = re.findall(pattern, user_message, re.IGNORECASE)
                current_factories.update([match.strip() for match in matches])

            # Look for customer/market names
            customer_patterns = [
                r'customers?\s*\([^)]*?([A-Za-z][A-Za-z0-9\s\-_]*?):\s*\d+',
                r'markets?\s*\([^)]*?([A-Za-z][A-Za-z0-9\s\-_]*?):\s*\d+'
            ]

            current_customers = set()
            for pattern in customer_patterns:
                matches = re.findall(pattern, user_message, re.IGNORECASE)
                current_customers.update([match.strip() for match in matches])

            # Compare with previous entities
            previous_factories = set(last_params.get("plants", []))
            previous_customers = set(last_params.get("markets", []))

            # If we found new entities and they're different from previous ones, it's a new problem
            factories_changed = current_factories and current_factories != previous_factories
            customers_changed = current_customers and current_customers != previous_customers

            return factories_changed or customers_changed

        except Exception:
            # If detection fails, assume it's a new problem to be safe
            return True

    def _provide_capabilities_info(self, session_id: str, last_solution: Dict) -> Dict[str, Any]:
        """Provide information about available analysis capabilities"""

        content = f"📋 **Available Analysis Types**\n\n"
        content += f"For your {last_solution.get('problem_type', 'optimization').lower()} problem, I can provide:\n\n"
        content += f"🔍 **Sensitivity Analysis**\n"
        content += f"• Ask: 'How does [parameter] affect [objective]?'\n"
        content += f"• Example: 'How does capacity affect total cost?'\n\n"
        content += f"📊 **Visualizations**\n"
        content += f"• Ask: 'Show me plots/charts/graphs'\n"
        content += f"• Displays solution flows and relationships\n\n"
        content += f"🔄 **What-if Scenarios**\n"
        content += f"• Ask: 'What if I change [parameter] to [value]?'\n"
        content += f"• Example: 'What if I double the capacity?'\n\n"
        content += f"❓ **Problem Questions**\n"
        content += f"• 'What is the objective function?'\n"
        content += f"• 'How many variables/entities are there?'\n"
        content += f"• 'What are the constraints?'"

        response = {
            "success": True,
            "content": content,
            "is_follow_up": True,
            "follow_up_type": "question"
        }

        self.memory.add_message(session_id, "assistant", content, response)
        return response

    def _provide_objective_info(self, session_id: str, last_solution: Dict) -> Dict[str, Any]:
        """Provide information about the objective function"""

        problem_type = last_solution.get('problem_type', 'Unknown')
        solution = last_solution.get('solution', {})

        if problem_type == "TRANSPORTATION":
            objective_value = solution.get('objective_thousand_usd', 0)
            content = f"🎯 **Objective Function**\n\n"
            content += f"**Type:** Minimization problem\n"
            content += f"**Goal:** Minimize total transportation cost\n"
            content += f"**Current Value:** ${objective_value:.2f}k USD\n\n"
            content += f"**What we're optimizing:**\n"
            content += f"• Find the cheapest way to ship products\n"
            content += f"• From production plants to customer markets\n"
            content += f"• While respecting capacity and demand constraints"
        else:
            content = f"🎯 **Objective Function**\n\n"
            content += f"**Problem Type:** {problem_type}\n"
            content += f"**Current Solution Value:** {solution.get('objective', 'N/A')}\n\n"
            content += f"This optimization problem seeks to find the best solution according to the defined objective."

        response = {
            "success": True,
            "content": content,
            "is_follow_up": True,
            "follow_up_type": "question"
        }

        self.memory.add_message(session_id, "assistant", content, response)
        return response

    def _provide_problem_size_info(self, session_id: str, last_solution: Dict) -> Dict[str, Any]:
        """Provide information about problem size/dimensions"""

        context = self.memory.get_context(session_id)
        last_params = context.get("last_params", {})
        problem_type = last_solution.get('problem_type', 'Unknown')

        content = f"📏 **Problem Dimensions**\n\n"

        if problem_type == "TRANSPORTATION":
            plants = last_params.get("plants", [])
            markets = last_params.get("markets", [])
            content += f"**Entities:**\n"
            content += f"• Production plants: {len(plants)} ({', '.join(plants)})\n"
            content += f"• Customer markets: {len(markets)} ({', '.join(markets)})\n"
            content += f"• Decision variables: {len(plants) * len(markets)} (shipment amounts)\n"
            content += f"• Constraints: {len(plants) + len(markets)} (capacity + demand)"
        else:
            content += f"**Problem Type:** {problem_type}\n"
            content += f"**Variables:** Available in solution data\n"
            content += f"**Constraints:** Problem-specific"

        response = {
            "success": True,
            "content": content,
            "is_follow_up": True,
            "follow_up_type": "question"
        }

        self.memory.add_message(session_id, "assistant", content, response)
        return response

    def _provide_constraints_info(self, session_id: str, last_solution: Dict) -> Dict[str, Any]:
        """Provide information about problem constraints"""

        problem_type = last_solution.get('problem_type', 'Unknown')

        content = f"⚖️ **Problem Constraints**\n\n"

        if problem_type == "TRANSPORTATION":
            content += f"**Supply Constraints:**\n"
            content += f"• Each plant cannot ship more than its production capacity\n"
            content += f"• Ensures we don't exceed what we can produce\n\n"
            content += f"**Demand Constraints:**\n"
            content += f"• Each market must receive at least its required demand\n"
            content += f"• Ensures all customer needs are met\n\n"
            content += f"**Non-negativity:**\n"
            content += f"• All shipment quantities must be ≥ 0\n"
            content += f"• Cannot ship negative amounts"
        else:
            content += f"**Problem Type:** {problem_type}\n"
            content += f"**Constraints:** Problem-specific constraints apply\n"
            content += f"These ensure the solution is feasible and realistic."

        response = {
            "success": True,
            "content": content,
            "is_follow_up": True,
            "follow_up_type": "question"
        }

        self.memory.add_message(session_id, "assistant", content, response)
        return response