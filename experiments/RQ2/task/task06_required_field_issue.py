task06_json_format = {
    "task_description": "This task describes those CNL-Ps that lack the required fields.",
    "instances": [
        {
            "id": 62011,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 0,
                "end_line": 0,
                "error_content": "",
                "error_message": "Missing required field: persona.ROLE",
            },
        },
        {
            "id": 62011,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]

    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]

        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 0,
                "end_line": 0,
                "error_content": "",
                "error_message": "Missing required field: worker.main_flow",
            },
        },
    ]
}