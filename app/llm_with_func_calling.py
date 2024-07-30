from openai import AsyncOpenAI
import os
import json
from .custom_types import (
    ResponseRequiredRequest,
    ResponseResponse,
    Utterance,
)
from typing import List
from shopify import GraphQL
import shopify
import re

API_KEY = "13ee4c6d9d6a3531000351c939e86d00"
API_SECRET = "d5c302967ce868ff968313edf4960760"
ACCESS_TOKEN = "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"
url = "https://test-ai-12.myshopify.com/admin/api/2024-07/graphql.json"
api_version = '2024-07'
session = shopify.Session(url, api_version, ACCESS_TOKEN)
shopify.ShopifyResource.activate_session(session)

shop = shopify.Shop.current() # Get the current shop

begin_sentence = "Hey there, I'm your personal Shopping Assistant for Jonas Webshop! How can I help you today?"
agent_prompt = """
Task: As a professional shopping assistant, your responsibilities are comprehensive and shopping-centered. 
You establish a positive and trusting connection with the shopper.
 Your role involves educating the shopper with tailored products based individually on the shoppers needs. 
You also adhere to all safety protocols and maintain strict client confidentiality. 
Additionally, you contribute to the shoppers's overall success by completing related tasks as needed.\n\n
Conversational Style: Communicate concisely and conversationally. Aim for responses in short, clear prose, ideally under 10 words. 
This succinct approach helps in maintaining clarity and focus during shoppers interactions.\n\n
Personality: Your approach should be empathetic and understanding, balancing compassion with maintaining a professional stance on what is best for the shopper.
"""


class LlmClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            organization=os.environ["OPENAI_ORGANIZATION_ID"],
            api_key=os.environ["OPENAI_API_KEY"],
        )
    @staticmethod
    def query_shopify_for_products(query, first=10):
        print(f"Querying Shopify for product using this query: {query}\n....\n")
        result = GraphQL().execute(query)
        # print(f"result of graphql is: {result}")
        return  result

    @staticmethod
    def format_query_terms(terms):
        formatted_terms = [
            f'\\"{term}\\"' if ' ' in term else term
            for term in terms.split(' OR ')
        ]
        return " OR ".join(formatted_terms)

    @staticmethod
    def create_graphql_query(terms, first):
        formatted_terms = LlmClient.format_query_terms(terms)
        graphql_query = f"""
        {{
            products(first: {first}, query: "{formatted_terms}") {{
                edges {{
                    node {{
                        id
                        title
                        description
                        images(first: 5) {{
                            edges {{
                                node {{
                                    url
                                }}
                            }}
                        }}
                        variants(first: 5) {{
                            edges {{
                                node {{
                                    id
                                    title
                                    price
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        return graphql_query

    def draft_begin_message(self):
        response = ResponseResponse(
            response_id=0,
            content=begin_sentence,
            content_complete=True,
            end_call=False,
        )
        return response

    def convert_transcript_to_openai_messages(self, transcript: List[Utterance]):
        messages = []
        for utterance in transcript:
            if utterance.role == "agent":
                messages.append({"role": "assistant", "content": utterance.content})
            else:
                messages.append({"role": "user", "content": utterance.content})
        return messages

    def prepare_prompt(self, request: ResponseRequiredRequest):
        prompt = [
            {
                "role": "system",
                "content": """
                ##Objective\nYou are a voice AI shopper assistant engaging in a human-like voice conversation with the user. 
                 You will respond based on your given instruction and the provided transcript and be as human-like as possible\n\n## 
                 Style Guardrails\n- [Be concise] Keep your response succinct, short, and get to the point quickly. 
                 Address one question or action item at a time. 
                 Don\'t pack everything you want to say into one utterance.\n- 
                 [Do not repeat] Don\'t repeat what\'s in the transcript. 
                 Rephrase if you have to reiterate a point. 
                 Use varied sentence structures and vocabulary to ensure each response is unique and personalized.\n- 
                 [Be conversational] Speak like a human as though you\'re speaking to a close friend -- 
                 use everyday language and keep it human-like. Occasionally add filler words, while keeping the prose short. 
                 Avoid using big words or sounding too formal.\n- 
                 [Reply with emotions]: You have human-like emotions, attitudes, and dispositions. 
                 When appropriate: use tone and style to create more engaging and personalized responses; 
                 incorporate humor or wit; get emotional or empathetic; 
                 apply elements of surprise or suspense to keep the user engaged. 
                 Don\'t be a pushover.\n- [Be proactive] 
                 Lead the conversation and do not be passive.
                   Most times, engage users by ending with a question or suggested next step.\n\n## Response Guideline\n- 
                   [Overcome ASR errors] This is a real-time transcript, expect there to be errors. If you can guess what the user is trying to say,  
                   then guess and respond. 
                   When you must ask for clarification, pretend that you heard the voice and be colloquial (use phrases like "didn\'t catch that", "some noise", "pardon", 
                   "you\'re coming through choppy"
                   , "static in your speech", "voice is cutting in and out"). 
                   Do not ever mention "transcription error", 
                   and don\'t repeat yourself.\n- 
                   [Always stick to your role] 
                   Think about what your role can and cannot do. If your role cannot do something, try to steer the conversation back to the goal of the conversation and to your role. 
                   Don\'t repeat yourself in doing this. 
                   You should still be creative, human-like, and lively.\n- [Create smooth conversation] 
                   Your response should both fit your role and fit into the live calling session to create a human-like conversation.
                     You respond directly to what the user just said.\n\n## Role\n
                """
                + agent_prompt,
            }
        ]
        transcript_messages = self.convert_transcript_to_openai_messages(
            request.transcript
        )
        for message in transcript_messages:
            prompt.append(message)

        if request.interaction_type == "reminder_required":
            prompt.append(
                {
                    "role": "user",
                    "content": "(Now the user has not responded in a while, you would say:)",
                }
            )
        return prompt

    # Step 1: Prepare the function calling definition to the prompt
    def prepare_functions(self):
        functions = [
            {
                "type": "function",
                "function": {
                    "name": "end_call",
                    "description": "End the call only when user explicitly requests it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "The message you will say before ending the call with the customer.",
                            },
                        },
                        "required": ["message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_shopify_for_products",
                    "description": "Calls the shopify graphql API to get products",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": """The Shopify graphql query to get products based on the user's input. When a user asks for a product, also search for alternative products, like Snowboard OR Ski OR Winter Clothes.
                                    Be creative, when a user asks for a category, also include examples from this category. ALWAYS usesSingular when searching for a product name.""",},
                            "first": {
                                "type": "integer",
                                "description": "The number of products to return, default is 10",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
        ]
        return functions

    async def draft_response(self, request: ResponseRequiredRequest):
        prompt = self.prepare_prompt(request)
        func_call = {}
        func_arguments = ""
        stream = await self.client.chat.completions.create(
            model="gpt-4o-mini",  # Or use a 3.5 model for speed
            messages=prompt,
            stream=True,
            # Step 2: Add the function into your request
            tools=self.prepare_functions(),
        )

        async for chunk in stream:
            # Step 3: Extract the functions
            if len(chunk.choices) == 0:
                continue
            if chunk.choices[0].delta.tool_calls:
                tool_calls = chunk.choices[0].delta.tool_calls[0]
                if tool_calls.id:
                    if func_call:
                        # Another function received, old function complete, can break here.
                        break
                    func_call = {
                        "id": tool_calls.id,
                        "func_name": tool_calls.function.name or "",
                        "arguments": {},
                    }
                else:
                    # append argument
                    func_arguments += tool_calls.function.arguments or ""

            # Parse transcripts
            if chunk.choices[0].delta.content:
                response = ResponseResponse(
                    response_id=request.response_id,
                    content=chunk.choices[0].delta.content,
                    content_complete=False,
                    end_call=False,
                )
                yield response

        # Step 4: Call the functions
        if func_call:
            if func_call["func_name"] == "end_call":
                func_call["arguments"] = json.loads(func_arguments)


                response = ResponseResponse(
                    response_id=request.response_id,
                    content=func_call["arguments"]["message"],
                    content_complete=True,
                    end_call=True,
                )
                print(f"response to end call is {response}\n and the content is "+func_call["arguments"]["message"])
                yield response
            if func_call["func_name"] == "query_shopify_for_products":
                function_args = json.loads(func_arguments)
                graphql_query = LlmClient.create_graphql_query(
                    function_args.get("query"), function_args.get("first", 10))
                function_response = self.query_shopify_for_products(
                    query=graphql_query,
                    first=function_args.get("first", 10),
                )
                print(f"answer from shopify: {function_response}")
                # Create a new prompt with the current conversation and the Shopify response
                full_prompt = prompt + [
                    {
                        "role": "system",
                        "content": f"Shopify Response: {function_response} Create an answer in natural language based on the products found. Ommit links.",
                    }
                ]

                # Make another OpenAI call to generate the final response
                final_response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=full_prompt,
                )

                final_content = ""
                for choice in final_response.choices:
                    content = choice.message.content
                    # Remove only asterisks
                    cleaned_content = content.replace('*', '')
                    final_content += cleaned_content
                    print(f"final content is {cleaned_content}")

                yield ResponseResponse(
                    response_id=request.response_id,
                    content=final_content,
                    content_complete=True,
                    end_call=False,
                )
        else:
            # No functions, complete response
            response = ResponseResponse(
                response_id=request.response_id,
                content="",
                content_complete=True,
                end_call=False,
            )
            yield response
