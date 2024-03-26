from typing import AsyncGenerator, Tuple

from schemas.documentation_generation import LlmModelEnum
from services.data_service import DataService, get_data_service
from services.documentation_service import DocumentationService, get_documentation_service
from services.rag_service.search_service import SearchService, get_search_service
from dotenv import load_dotenv
from services._prompts import (
    CHATBOT_SYS_PROMPT,
    CHATBOT_FALLBACK_SYS_PROMPT
)
import firebase_admin
import os
import asyncio
from collections import namedtuple

Relevant_Doc = namedtuple('Relevant_Doc', ['score', 'doc_content', 'doc_path'])

class WrongFormattingError(Exception):
    def __init__(self, message="Wrong formatting detected"):
        self.message = message
        super().__init__(self.message)

class InvalidAction(Exception):
    def __init__(self, message="Invalid action detected"):
        self.message = message
        super().__init__(self.message)

class ChatService:
    def __init__(
        self,
        search_service: SearchService,
        documentation_service: DocumentationService,
        data_service: DataService,
    ):
        self.search_service = search_service
        self.documentation_service = documentation_service
        self.data_service = data_service

    async def chat(self, repo_id: str, query: str, user_id: str, model: LlmModelEnum) -> AsyncGenerator[dict, None]:
        max_steps = 4
        chat_history = [{"role": "system", "content": CHATBOT_SYS_PROMPT}, {"role": "user", "content": f"Question: {query}"}]
    
        for i in range(max_steps):
            chat_completion = await self.documentation_service.llm_client.generate_messages(
                model=model,
                messages=chat_history,
                temperature=0.4,
                max_tokens=1024,
            )
            llm_output = chat_completion.choices[0].message.content
            chat_history.append({"role": "assistant", "content": llm_output})
            try:
                thought, action = self.parse_step(llm_output)
                action, action_input = self.extract_action(action)
                yield {"action": action, "output": action_input}
                if (action == "Finish"):
                    return
                output = await self.execute_action(action, action_input, repo_id, user_id)
                # print(f"Thought: {thought}")
                # print(f"Action: {action}")
                # print(f"Result: {output}")
                # print("=========================")
                chat_history.pop()
                chat_history.append({"role": "assistant", "content": f"Thought: {thought}\n\nAction: {action}"})
                chat_history.append({"role": "user", "content": f"Result: {output}"})
            except Exception as e:
                # We could catch the custom error types and let the Agent fix its course but the prompt
                # is good enough and remedying these errors that are far in between is doubling the runtime.
                # Using the fallback prompt is much more efficient with comparable a
                print(e)
                break
        # Use fallback prompt
        relevant_docs = await self.search(repo_id, query)
        chat_history = [{"role": "system", "content": CHATBOT_FALLBACK_SYS_PROMPT}, {"role": "user", "content": f"Question: {query}\n{relevant_docs}"}]
        chat_completion = await self.documentation_service.llm_client.generate_messages(
            model=model,
            messages=chat_history,
            temperature=0.4,
            max_tokens=512,
        )
        llm_output = chat_completion.choices[0].message.content
        yield {"action": "Finish", "output": llm_output}
        
        
    def parse_step(self, agent_output):
        thought_start = agent_output.find('Thought')
        action_start = agent_output.find('Action')
        
        if thought_start == -1:
            raise WrongFormattingError('Cannot extract the Thought step. Recall that the format is Thought: "Your Thought Here"')
        if action_start == -1:
            raise WrongFormattingError('Cannot extract the Action step. Recall that the format is Action: Search["Your Query Here"] or Action: Finish["Your Answer Here"]')
        
        thought = self.extract_step(agent_output[thought_start+len("Thought") : action_start])
        action = self.extract_step(agent_output[action_start+len("Action"):])
        
        return thought, action

    def extract_step(self, unparsed_step):
        # Skip all spaces and leading colon if exists
        step = unparsed_step.lstrip(':').strip()        
        # Drop quotes on the outside if they exist
        step = step.strip('\'"')
        return step
    
    def extract_action(self, action):
        if action.startswith("Search"):
            func_input = action[len("Search"):].strip(" []\"'")
            return "Search", func_input
        elif action.startswith("Finish"):
            func_input = action[len("Finish"):].strip(" []\"'")
            return "Finish", func_input
        raise InvalidAction('Cannot extract the Action type. Recall that the only allowed Actions types are Action: Search["Your Query Here"] or Action: Finish["Your Answer Here"]')

    async def execute_action(self, action, input, repo_id, user_id):
        if action == "Search":
            return await self.search(repo_id, input, user_id)
        elif action == "Finish":
            return input
        else:
            raise InvalidAction('Cannot execute the Action. Recall that the only allowed Actions types are Search and Finish')

    async def search(self, repo_id, input, user_id):
        search_results = await self.search_service.search(repo_id, input)
        docs = {}
        for search_result in search_results:
            doc_id, score = search_result["doc_id"], search_result["score"]
            if doc_id not in docs and score > 0.6:
                document = self.data_service.get_user_documentation(user_id, doc_id)
                docs[doc_id] = Relevant_Doc(score, document.markdown_content, document.relative_path)
        
        documentation_summary = []
        documentation = []
        for i, d in enumerate(docs):
            relevant_document = docs[d]
            score, doc_content, doc_path = relevant_document.score, relevant_document.doc_content, relevant_document.doc_path
            documentation_summary.append(f"{i+1}. {doc_path} with a relevancy score of {score}.\n")
            documentation.append(f"{doc_content}\n")
        output = f"There are {len(docs)} relevant document(s).\n" + ''.join(documentation_summary) + "\n" + '\n\n'.join(documentation)
        return output
def get_chat_service() -> ChatService:
    search_service = get_search_service()
    documentation_service = get_documentation_service()
    data_service = get_data_service()
    return ChatService(search_service, documentation_service, data_service)

if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None,
        options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )
    chat_service = get_chat_service()
    repo_id = "3153f0a7-09ef-4a12-be4f-3de3b8defda3"
    query = "how can i create a game board object?"
    user_id = "qZ6GC61uBPha2bbMirUy3RgY6w92"
    async def print_chat_contents():
        async for content in chat_service.chat(repo_id, query, user_id, LlmModelEnum.MIXTRAL):
            print(content)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(print_chat_contents())