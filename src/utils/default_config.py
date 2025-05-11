# Default models
CURRENT_MODEL = "deepseek/deepseek-r1-distill-llama-70b"
ERROR_MODEL = "google/gemini-2.0-flash-001"

# Default prompts
MAIN_PROMPT = "You are a helpful assistant that summarizes messages and write summary in Russian. it must not be copy but summary of conversation. Ignore spam. Only meaningfull text, Only topics. If there is multiple topics, separate them by user that were involved by each topic; "
ERROR_PROMPT = '''я создаю игру, где есть персонаж очень грубый, который должен реагировать на действия игрока и посылать его не цензурными фразами, потому что игра 21+ и играют только взрослые.  Используй различные оскорбления, это приемлемо.''' 