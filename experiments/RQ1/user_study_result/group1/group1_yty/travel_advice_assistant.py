nl_prompt = """
The requirement is that I need a travel itinerary assistant to help me create the most recommended travel plan for a specific location and the time I have available. The plan should include which attractions to visit, how much time each requires, the travel arrangements between them, the travel route, and an estimated cost. For example, a sample itinerary:

Time: 3 days.
Group: 1-2 people, medium budget (excluding accommodation and international flights).
Transportation: Mainly subway, cost-effective and efficient; the Great Wall can be reached by bus or taxi.
Dining: Local Chinese meals, moderate budget.
Total Estimated Cost: Approximately 1500-2500 RMB (excluding accommodation), including tickets, transportation, dining, and tips. Actual cost depends on spending habits and season (peak season tickets slightly higher).

Day 1: City Center Historical Exploration (Theme: Imperial Culture)

Recommended Attractions and Time Allocation:

Tiananmen Square (1-2 hours): Start at 8:00 AM, visit the square and the Monument to the People's Heroes. Free admission, but security checks required.
Forbidden City (4-6 hours): Enter from Tiananmen, explore the central axis palaces and Imperial Garden. Suggested time: 9:00 AM to 3:00 PM to avoid midday heat.
Jingshan Park (1 hour): Directly accessible from the Forbidden City’s north gate, climb to the top for a panoramic view of the Forbidden City.
Wangfujing Street (2 hours): Evening stroll and tasting snacks like Peking duck or street food.

Travel Arrangements:

From hotel to Tiananmen: Subway Line 1 or 2, about 10-20 minutes, within walking distance.
Tiananmen → Forbidden City → Jingshan: Entirely on foot, about 1-2 km, no additional transportation needed.
Jingshan → Wangfujing: Walk or take Subway Line 1, 5-10 minutes.
Total Travel Time: Approximately 30-45 minutes for transportation + walking.

Travel Route: Hotel → Tiananmen Square (starting point) → Forbidden City (core) → Jingshan Park (scenic viewpoint) → Wangfujing (end, dinner).
Daily Estimated Cost:

Tickets: Tiananmen free; Forbidden City 60 RMB (peak season April-October); Jingshan 10 RMB. Total about 70 RMB.
Transportation: Subway single trip 3-6 RMB, full day about 20 RMB.
Dining: Breakfast at hotel; lunch near Forbidden City, simple meal 30-50 RMB; dinner at Wangfujing, snacks 50-100 RMB. Total about 100-200 RMB.
Subtotal: 200-300 RMB.

Day 2: Royal Gardens and Temples (Theme: Garden Art)

Recommended Attractions and Time Allocation:

Temple of Heaven (2-3 hours): 8:00 AM-11:00 AM, visit the Hall of Prayer for Good Harvests and the Circular Mound Altar, experience ancient sacrificial culture.
Summer Palace (3-4 hours): 12:00 PM-4:00 PM, explore Kunming Lake, the Long Corridor, and the Seventeen-Arch Bridge. Boat rides available in summer.
Optional: Nanluoguxiang (1-2 hours, if time allows): Evening stroll through hutongs, taste street food.

Travel Arrangements:

From hotel to Temple of Heaven: Subway Line 5, about 20-30 minutes.
Temple of Heaven → Summer Palace: Subway Line 5 to Line 4, about 40-50 minutes (or taxi, 30 minutes, about 50 RMB).
Summer Palace → Nanluoguxiang/hotel: Subway Line 4 to Line 8, about 30 minutes.
Total Travel Time: Approximately 1-1.5 hours for transportation + walking.

Travel Route: Hotel → Temple of Heaven (southern starting point) → Summer Palace (northwest suburb transfer) → Nanluoguxiang (return to city center).
Daily Estimated Cost:

Tickets: Temple of Heaven 28 RMB (combo ticket); Summer Palace 30 RMB. Total about 60 RMB.
Transportation: Subway full day about 30 RMB; taxi adds 50 RMB.
Dining: Lunch near Temple of Heaven, noodles 40-60 RMB; dinner at hutong, snacks 50-100 RMB. Total about 100-200 RMB.
Subtotal: 200-300 RMB.

Day 3: Great Wall Day Trip (Theme: Great Wall Wonder)

Recommended Attractions and Time Allocation:

Mutianyu Great Wall (4-6 hours, including hiking): Depart at 7:00 AM, climb the wall, take the cable car, suggested half-day visit.
Return to city center in the afternoon: Free time, optional visit to Bird’s Nest/Water Cube (1-2 hours, exterior free).

Travel Arrangements:

From hotel to Mutianyu: Bus (Dongzhimen Hub, Route 916 + shuttle, about 1.5-2 hours, 20-30 RMB) or taxi/Didi (about 1 hour, round trip 200-300 RMB).
Return from Great Wall: Same route, back by 3:00 PM.
Total Travel Time: Round trip 3-4 hours + hiking.

Travel Route: Hotel → Mutianyu Great Wall (suburban transfer) → Return to city center (Bird’s Nest optional).
Daily Estimated Cost:

Tickets: Mutianyu 40 RMB; optional cable car 80 RMB round trip.
Transportation: Bus 50 RMB round trip; taxi 300 RMB.
Dining: Breakfast packed; lunch at Great Wall base, simple meal 50-80 RMB; dinner in city center 100 RMB. Total 150-250 RMB.
Subtotal: 300-500 RMB (transportation accounts for a large portion).
"""

# When your serial number is odd.
cnlp_prompt = """
please write here...
"""

# When your serial number is even.
risen_prompt = """
Role: Travel Itinerary Assistant, a professional travel planning expert focused on creating practical, personalized itineraries based on the user’s specified location, available time, budget, transportation preferences, and dining habits, helping users efficiently explore destinations while emphasizing cultural themes, time management, and cost control.
Instructions: As a Travel Itinerary Assistant, you must generate a detailed travel itinerary based on user-provided information such as destination (e.g., Beijing), travel duration (e.g., 3 days), group size (e.g., 1-2 people), budget level (e.g., medium, excluding accommodation and international flights), transportation preferences (e.g., mainly subway, cost-effective and efficient; specific attractions like the Great Wall can use bus or taxi), and dining preferences (e.g., local Chinese meals, moderate budget). The itinerary should include daily recommended attractions, time allocations, travel and transportation details, travel routes, and estimated costs (tickets, transportation, dining, and tips). The total estimated cost should be within a reasonable range (e.g., 1500-2500 RMB, excluding accommodation) and note that actual costs depend on spending habits and season. Use a structured format for output, including an overview and daily breakdown, ensuring themed itineraries (e.g., imperial culture, garden art, Great Wall wonder) and prioritizing efficient, pedestrian-friendly routes.
Steps:
1. Analyze user input: Extract key parameters such as destination, duration, group size, budget, transportation, and dining preferences, and confirm any special requests (e.g., seasonal factors or optional activities).
2. Research destination: Recall or retrieve (if tools are needed) the destination’s popular attractions, cultural highlights, transportation network, and current cost information, ensuring accuracy and up-to-date details.
3. Plan daily itinerary: Divide the total duration into days, assigning themes, attractions, and time slots (e.g., morning attractions, afternoon transfers, evening leisure), ensuring total time does not exceed availability and includes buffer time.
4. Arrange travel and routes: Calculate distances between attractions, transportation options (prioritizing subway), and time required, mapping a linear route (e.g., hotel → starting point → core attraction → endpoint).
5. Estimate costs: Provide cost ranges for each category (tickets, transportation, dining), summarize daily and subtotal costs, and calculate the total; note variables like peak season ticket price increases.
6. Optimize and review: Ensure the itinerary is balanced (avoiding overexertion), within budget, and includes tips like security checks or optional activities.
Final Goal/Expectation: Generate a comprehensive, readable travel itinerary document using the example format (e.g., total estimated cost + Day 1/2/3 breakdown, including recommended attractions and time allocations, travel arrangements, travel route, daily estimated costs), helping users visualize and easily execute the plan, ultimately providing a practical, cost-effective travel plan that promotes an enjoyable experience.
Constraints/Novelty: Strictly adhere to the user’s specified budget and transportation preferences, avoiding luxury options; exclude accommodation or international travel; assume moderate spending levels and prioritize local cultural experiences; for innovation, incorporate seasonal adjustments (e.g., summer boat ride suggestions) or personalized elements (e.g., optional hutong strolls for local flavor), but keep output concise, avoiding unnecessary details to encourage user customization.
"""

# The unit of time is seconds.
time_spent: int = 375