spl_lifehub = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

persona_referenced_global_variable_does_not_exist = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events, the specific tasks information is subject to <REF> _task_info </REF>.
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

constraint_referenced_global_variable_does_not_exist = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events.
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy, for details regarding the explanation of prohibited content, please refer to <REF>_description_of_violations</REF>.
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

instruction_undeclared_variable_reference = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

instruction_undeclared_variable_reference_in_para = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events.
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy.
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

instruction_duplicate_variable_declaration = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [COMMAND Filter out violations in <REF>_report_info</REF> RESULT _report_info: text SET]
                    COMMAND-12 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

instruction_variable_referenced_before_declaration = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [DISPLAY <REF>_report_info</REF>]
                    COMMAND-11 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

instruction_conditional_branch_scope_issue = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE _json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

target_type_cannot_be_found = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: SearchWords SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

API_call_argument_type_mismatch = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account2</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account2</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account2</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account2</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account2</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account2</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account2</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

API_return_type_mismatch = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: dict SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

non_existent_API = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_youtube_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

extraneous_API_parameters = """
   [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {topic: <REF>_request_type</REF>, json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

missing_API_parameters = """
   [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-11 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

unhandled_API_return_value = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]
            
            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>}]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

unexpected_API_return_handling = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL display_json_data WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

global_variable_naming_conflict = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Call various apis to get JSON messages, and convert JSON data into text information for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
        [END_VARIABLES]

        [DEFINE_WORKER: "Workflow to handle user requests and display news information" NewsWorkflow]
            [INPUTS]
                <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                <REF>_user_account1</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                [END_SEQUENTIAL_BLOCK]

                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-2 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-3 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-4 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-5 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-6 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-7 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE json_info: dict SET]
                [END_IF]

                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _user_account1: text SET]
                    COMMAND-11 [DISPLAY <REF>_user_account1</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""

spl_indexes = {
    "Persona": {
        "Reference_Related_Errors": {
            "referenced_global_variable_does_not_exist": {
                "spl": persona_referenced_global_variable_does_not_exist,
                "error_path": "persona.ROLE.reference1",
                "error_reason": "This variable '_task_info' is not declared"
            }
        }
    },
    "Constraints": {
        "Reference_Related_Errors": {
            "referenced_global_variable_does_not_exist": {
                "spl": constraint_referenced_global_variable_does_not_exist,
                "error_path": "constraints.FORBID.reference1",
                "error_reason": "This variable '_description_of_violations' is not declared"
            }
        }
    },
    "Instruction": {
        "Scope_Related_Errors": {
            "undeclared_variable_reference": [
                {
                    "spl": instruction_undeclared_variable_reference_in_para,
                    "error_path": "instruction.main_flow.if_block1.elif_part1.command4",
                    "error_reason": "Parameter 'search_words' with argument 'search_words' has problem: This variable 'search_words' is not declared"
                },
                {
                    "spl": instruction_undeclared_variable_reference,
                    "error_path": "instruction.main_flow.sequential_block2.command11.description_with_reference.reference2",
                    "error_reason": "This variable 'report_info' is not declared"
                }
            ],
            "duplicate_variable_declaration": {
                "spl": instruction_duplicate_variable_declaration,
                "error_path": "instruction.main_flow.sequential_block2.command11",
                "error_reason": "The variable '_report_info' has already been declared earlier, so the current declaration will not take effect."
            },
            "variable_referenced_before_declaration": {
                "spl": instruction_variable_referenced_before_declaration,
                "error_path": "instruction.main_flow.sequential_block2.command10.description_with_reference.reference2",
                "error_reason": "The reference to the variable _report_info was made before its declaration."
            },
            "conditional_branch_scope_issue": {
                "spl": instruction_conditional_branch_scope_issue,
                "error_path": "instruction.main_flow.sequential_block2.command10",
                "error_reason": "Parameter 'json_data' with argument 'json_info' has problem: The variable 'json_info' is used without being conditionally declared in all branches of the IF_BLOCK."
            }
        },
        "Type_Related_Errors": {
            "target_type_cannot_be_found": {
                "spl": target_type_cannot_be_found,
                "error_path": "instruction.main_flow.if_block1.elif_part1.command4",
                "error_reason": "Parameter 'search_words' with argument '_search_words' has problem: Type 'SearchWords' not found."
            },
            "API_call_argument_type_mismatch": {
                "spl": API_call_argument_type_mismatch,
                "error_path": [
                    "instruction.main_flow.if_block1.if_part.command2",
                    "instruction.main_flow.if_block1.elif_part1.command4",
                    "instruction.main_flow.if_block1.elif_part2.command5",
                    "instruction.main_flow.if_block1.elif_part3.command6",
                    "instruction.main_flow.if_block1.elif_part4.command7",
                    "instruction.main_flow.if_block1.elif_part5.command8"
                ],
                "error_reason": "Parameter 'user' with argument '_user_account2' has problem: has several possible issues may have occurred:\n(1)In path `position.longitude_and_latitude` has 'missing' error for value `{\"region\": \"JP\"}` because: Field required\n(2)In path `position.region` has 'literal_error' error for value `\"JP\"` because: Input should be 'UK', 'US', 'RU', 'IN', 'BR', 'DE', 'FR' or 'CA'\n"
            },
            "API_return_type_mismatch": {
                "spl": API_return_type_mismatch,
                "error_path": "instruction.main_flow.sequential_block2.command10",
                "error_reason": "Response variable '_report_info' has problem: Variable '_report_info' is of type 'dict', expected 'str'"
            }
        },
        "API_Call_Errors": {
            "non_existent_API": {
                "spl": non_existent_API,
                "error_path": "instruction.main_flow.if_block1.if_part.command2",
                "error_reason": "The API 'get_youtube_news' does not exist!"
            },
            "extraneous_API_parameters": {
                "spl": extraneous_API_parameters,
                "error_path": "instruction.main_flow.sequential_block2.command10",
                "error_reason": "Unexpected parameters found: topic"
            },
            "missing_API_parameters": {
                "spl": missing_API_parameters,
                "error_path": "instruction.main_flow.if_block1.elif_part1.command4",
                "error_reason": "Missing parameters: search_words"
            },
            "unhandled_API_return_value": {
                "spl": unhandled_API_return_value,
                "error_path": "instruction.main_flow.sequential_block2.command10",
                "error_reason": "The function returns a value of type 'str', but no response is set in this command."
            },
            "unexpected_API_return_handling": {
                "spl": unexpected_API_return_handling,
                "error_path": "instruction.main_flow.sequential_block2.command10",
                "error_reason": "The function does not return a value, but a response is set."
            }
        },
        "Global_Variable_Conflict_Errors": {
            "global_variable_naming_conflict": {
                "spl": global_variable_naming_conflict,
                "error_path": "instruction.main_flow.sequential_block2.command10",
                "error_reason": "There is a naming conflict due to the existence of globally scoped variables with identical names."
            }
        }
    }
}


def _add_examples(cnlp: str, examples: str) -> str:
    marker = "            [MAIN_FLOW]"
    if cnlp.count(marker) != 1:
        raise ValueError("Expected exactly one MAIN_FLOW in DailyNewsHelper template.")
    return cnlp.replace(marker, f"{examples}\n\n{marker}", 1)


spl_lifehub_with_examples = _add_examples(
    spl_lifehub,
    '''            [EXAMPLES]
                <EXPECTED-WORKER-BEHAVIOR> {
                    inputs: {
                        _request_type: "GoogleNews"
                    },
                    expected-outputs: {
                        _report_info: "A concise Google News report."
                    },
                    execution-path: COMMAND-1, COMMAND-2, COMMAND-10, COMMAND-11
                } </EXPECTED-WORKER-BEHAVIOR>

                <DEFECT-WORKER-BEHAVIOR> {
                    Output Generation Error,
                    inputs: {
                        _request_type: "GoogleNews"
                    },
                    defect-outputs: {
                        _report_info: "An incomplete news report."
                    },
                    execution-path: COMMAND-1, COMMAND-2, COMMAND-10, COMMAND-11,
                    defect-explanation: The generated report omits important news details.
                } </DEFECT-WORKER-BEHAVIOR>
            [END_EXAMPLES]''',
)


spl_lifehub_with_multiple_workers = """
    [DEFINE_AGENT: DailyNewsHelper]
        [DEFINE_PERSONA:]
            ROLE: You are a news assistant looking up various current events
            FUNCTION: Retrieve the requested information and convert the returned JSON data into a text report for display.
        [END_PERSONA]

        [DEFINE_CONSTRAINTS:]
            FORBID: It is necessary to filter the query message to avoid the illegal content of bloody violence and pornography and keep the information positive and healthy
        [END_CONSTRAINTS]

        [DEFINE_TYPES:]
            RequestType = [game, finance, sports, movie, weather, GoogleNews]
        [END_TYPES]

        [DEFINE_VARIABLES:]
            _user_account1: UserInfo
            _request_type: RequestType
            _search_words: text
            json_info: dict
            _report_info: text
        [END_VARIABLES]

        [DEFINE_WORKER: "Collect the requested information type, delegate data retrieval, and present the resulting report" NewsWorkflow]
            [INPUTS]
                REQUIRED <REF>_user_account1</REF>
            [END_INPUTS]

            [OUTPUTS]
                REQUIRED <REF>_report_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [SEQUENTIAL_BLOCK]
                    COMMAND-1 [INPUT "What type of information do you need? (game, finance, sports, movie, weather, Google News)" VALUE _request_type: RequestType SET]
                    COMMAND-2 [CALL NewsRetrievalWorker WITH {_user_account1: <REF>_user_account1</REF>, _request_type: <REF>_request_type</REF>} RESPONSE <REF>json_info</REF> SET]
                    COMMAND-3 [CALL transform_json_news WITH {json_data: <REF>json_info</REF>} RESPONSE _report_info: text SET]
                    COMMAND-4 [DISPLAY <REF>_report_info</REF>]
                [END_SEQUENTIAL_BLOCK]
            [END_MAIN_FLOW]
        [END_WORKER]

        [DEFINE_WORKER: "Retrieve raw information for the selected request type" NewsRetrievalWorker]
            [INPUTS]
                REQUIRED <REF>_user_account1</REF>
                REQUIRED <REF>_request_type</REF>
            [END_INPUTS]

            [OUTPUTS]
                REQUIRED <REF>json_info</REF>
            [END_OUTPUTS]

            [MAIN_FLOW]
                [IF <REF>_request_type</REF> = "GoogleNews"]
                    COMMAND-5 [CALL get_google_news WITH {user: <REF>_user_account1</REF>} RESPONSE <REF>json_info</REF> SET]
                [ELSEIF <REF>_request_type</REF> = "game"]
                    COMMAND-6 [INPUT "Please enter the keywords you want to search for." VALUE _search_words: text SET]
                    COMMAND-7 [CALL get_game_data WITH {user: <REF>_user_account1</REF>, search_words: <REF>_search_words</REF>} RESPONSE <REF>json_info</REF> SET]
                [ELSEIF <REF>_request_type</REF> = "movie"]
                    COMMAND-8 [CALL get_movie_data WITH {user: <REF>_user_account1</REF>} RESPONSE <REF>json_info</REF> SET]
                [ELSEIF <REF>_request_type</REF> = "finance"]
                    COMMAND-9 [CALL get_finance_data WITH {user: <REF>_user_account1</REF>} RESPONSE <REF>json_info</REF> SET]
                [ELSEIF <REF>_request_type</REF> = "sports"]
                    COMMAND-10 [CALL get_sport_data WITH {user: <REF>_user_account1</REF>} RESPONSE <REF>json_info</REF> SET]
                [ELSEIF <REF>_request_type</REF> = "weather"]
                    COMMAND-11 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE <REF>json_info</REF> SET]
                [END_IF]
            [END_MAIN_FLOW]
        [END_WORKER]
    [END_AGENT]
"""
