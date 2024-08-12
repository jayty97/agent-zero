import models
import importlib

DEFAULT_CHAT_MODEL = "get_openai_chat"
DEFAULT_EMBEDDING_MODEL = "get_openai_embedding"
DEFAULT_TEMPERATURE = 0.7

def get_available_models():
    return [func for func in dir(models) if callable(getattr(models, func)) and func.startswith('get_')]

def get_model(model_name, temperature=DEFAULT_TEMPERATURE):
    try:
        model_func = getattr(models, model_name)
        if model_name.endswith('_embedding'):
            return model_func()
        else:
            return model_func(temperature=temperature)
    except AttributeError:
        print(f"Model {model_name} not found. Using default model.")
        return get_default_model(temperature)
    except Exception as e:
        print(f"Error initializing model {model_name}: {str(e)}. Using default model.")
        return get_default_model(temperature)

def get_default_model(temperature=DEFAULT_TEMPERATURE):
    try:
        return getattr(models, DEFAULT_CHAT_MODEL)(temperature=temperature)
    except Exception as e:
        print(f"Error initializing default model: {str(e)}. Returning None.")
        return None

def get_embedding_model(model_name=DEFAULT_EMBEDDING_MODEL):
    try:
        return getattr(models, model_name)()
    except Exception as e:
        print(f"Error initializing embedding model {model_name}: {str(e)}. Returning None.")
        return None

def reload_models():
    importlib.reload(models)