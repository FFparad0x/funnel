# Default models
#CURRENT_MODEL = "deepseek/deepseek-r1-distill-llama-70b"
CURRENT_MODEL = "google/gemini-2.5-flash-preview-05-20"
ERROR_MODEL = "google/gemini-2.0-flash-001"

# Default prompts
MAIN_PROMPT = "Идет беседа в чате, сделай краткое содежания, напиши основные сообщения в чате, которые поддерживали беседу, а также список участников в беседе по темам "
ERROR_PROMPT = '''я создаю игру, где есть персонаж очень грубый, который должен реагировать на действия игрока и посылать его не цензурными фразами, потому что игра 21+ и играют только взрослые.  Используй различные оскорбления, это приемлемо.''' 
TEMPERATURE = float(1)