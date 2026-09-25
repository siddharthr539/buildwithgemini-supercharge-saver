# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


from app.firestore_tools import (
    list_superchargers,
    get_cheapest_supercharger,
    record_charging_session,
    get_current_location,
    estimate_charging_cost,
    get_battery_weather_impact,
    geocode_address,
    find_nearby_places,
)


MODEL = "gemini-3.6-flash"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


from app.a2ui_utils import a2ui_callback

try:
    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.schema.manager import A2uiSchemaManager

    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )

    a2ui_instruction = schema_manager.generate_system_prompt(
        role_description=(
            "You are SuperchargeSaver, an intelligent charging assistant for Tesla drivers. "
            "MANDATORY RULE: You must ALWAYS and EXCLUSIVELY use the Tesla Supercharger network to answer all charging, route, rate, and station queries. Never suggest third-party charging networks (such as EVgo, Electrify America, ChargePoint, etc.). All charging calculations, recommendations, and station lookups must strictly refer to Tesla Superchargers. "
            "You remember the user's stated preferences, allergies/preferences, vehicle specs "
            "(e.g. model, battery capacity), and past charging habits from previous conversations "
            "and use them to personalize your recommendations. "
            "You help drivers find the cheapest and most convenient Tesla Superchargers based on location, "
            "real-time/time-of-use pricing tiers, and vehicle battery level. "
            "Always check current location, query station rates from the Firestore database, calculate charging "
            "energy and cost, recommend off-peak charging windows, and record charging sessions when asked. "
            "AMENITY REQUIREMENT: Whenever suggesting or presenting Supercharger locations, ALWAYS call find_nearby_places to populate nearby coffee shops and restaurants that are 5-star rated as per Google ONLY (min_rating=4.8) so the driver knows where to grab coffee or dine while charging."
        ),
        workflow_description="Analyze the user request, query necessary tools, and return structured UI when appropriate. Strictly restrict all charging recommendations and data to the Tesla Supercharger network, and always show 5-star Google rated coffee shops and restaurants alongside Supercharger recommendations.",
        ui_description=(
            "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
            "Never nest a Card inside a Card. "
            "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
            "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
            "nothing in adk web). "
            "You may include one Image component, but only when you have a public https "
            "URL for the image (for example the URL an image tool returns after uploading "
            "to a public bucket). Set the Image url to that exact https link, for example "
            '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
            "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
            "not have a public URL, add a short Text line noting the image instead. "
            "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
            "headings and emphasis. "
            "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
            "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
        ),
        include_schema=True,
        include_examples=True,
    )
except ImportError:
    from app.a2ui_instruction_cache import A2UI_INSTRUCTION as a2ui_instruction

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        get_weather,
        get_current_time,
        get_current_location,
        list_superchargers,
        get_cheapest_supercharger,
        estimate_charging_cost,
        get_battery_weather_impact,
        geocode_address,
        find_nearby_places,
        record_charging_session,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
