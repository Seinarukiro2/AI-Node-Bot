import os
from dotenv import load_dotenv
from langchain.chains import RetrievalQA, LLMChain
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.memory import ConversationBufferMemory
# from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder, SystemMessage

load_dotenv()

class ClicktimeAIBot:
    def __init__(self):
        self.DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db")
        self.vectordb = None
        self.retriever = None
        self.qa = None
        self.memory = None

        # Initialize embeddings and vector database
        ollama_embeddings = OllamaEmbeddings(model="mistral")

        if not os.path.exists(self.DB_DIR):
            os.makedirs(self.DB_DIR)
        
        # Create Chroma vector database
        self.vectordb = Chroma(embedding_function=ollama_embeddings, persist_directory=self.DB_DIR)

        # Initialize memory
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        # If there are documents, load them and set retriever and QA chain
        if self.vectordb:
            self.retriever = self.vectordb.as_retriever(search_kwargs={"k": 3})
            llm = Ollama(model="mistral")
            self.qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=self.retriever, memory=self.memory)

    def load_data_from_url(self, url):
        loader = WebBaseLoader(url)
        return loader.load()

    def train_model_from_data(self, data):
        text_splitter = CharacterTextSplitter(separator='\n', 
                                              chunk_size=1000, 
                                              chunk_overlap=40)
        docs = text_splitter.split_documents(data)
        
        # Adding documents to vector database
        self.vectordb.add_documents(documents=docs)
        self.vectordb.persist()

        # Setting retriever and QA chain
        self.retriever = self.vectordb.as_retriever(search_kwargs={"k": 3})
        llm = Ollama(model="mistral")
        self.qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=self.retriever, memory=self.memory)

    def ask_question(self, prompt):
        if self.qa:
            response = self.qa(prompt)
            return response
        else:
            return "Model has not been trained yet. Please train the model first."

    def add_data_from_url(self, url):
        if self.vectordb:
            loader = WebBaseLoader(url)
            data = loader.load()
            docs = CharacterTextSplitter(separator='\n', chunk_size=1000, chunk_overlap=40).split_documents(data)
            self.vectordb.add_documents(documents=docs)
            self.vectordb.persist()
            return "Data added successfully."
        else:
            return "Vector database not initialized. Please train the model first."

# Example usage
if __name__ == "__main__":
    bot = ClicktimeAIBot()
    url = "http://example.com"  # Replace with actual URL
    data = bot.load_data_from_url(url)
    bot.train_model_from_data(data)
    response = bot.ask_question("Как установить ноду Allora?")
    print(response)
