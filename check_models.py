import google.generativeai as genai

genai.configure(api_key="AIzaSyAAtupEwzxGzEtLj6RAQeL5Kx2LcolMTSo")

models = genai.list_models()

for model in models:
    print(model.name)