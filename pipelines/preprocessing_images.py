import os
import cv2
from src.image_preprocessing import ImageAnalyzer, Filter

pasta_entrada = "data/raw_images/PSP_EXTRATLEITIMPL_220526_0408"
sufixo_saida = "_preprocessed"

# Pasta de saída: mesmo nome + "_preprocessed"
nome_pasta = os.path.basename(pasta_entrada)
pasta_saida = os.path.join(
    "data",
    "preprocessed_images",
    nome_pasta + sufixo_saida
)

os.makedirs(pasta_saida, exist_ok=True)

for nome_arquivo in os.listdir(pasta_entrada):

    # Só processa jpg/jpeg
    if not nome_arquivo.lower().endswith((".jpg", ".jpeg")):
        continue

    caminho = os.path.join(pasta_entrada, nome_arquivo)

    try:
        with open(caminho, "rb") as arquivo:

            # Analisa a imagem
            analisador = ImageAnalyzer(arquivo)
            brilho = analisador.brightness_status()
            ruido = analisador.noise_status()

            # Volta o cursor do arquivo para o início antes de ler de novo
            arquivo.seek(0)
            filtro = Filter(arquivo)

        # Aplica os filtros conforme o diagnóstico
        if brilho == "escura":
            filtro.increase_brightness()
        elif brilho == "clara":
            filtro.decrease_brightness()

        if ruido == "borrada":
            filtro.sharpen()
        elif ruido == "ruidosa":
            filtro.suavization()

        # Salva a imagem tratada
        cv2.imwrite(os.path.join(pasta_saida, nome_arquivo), filtro.image)
        print(f"{nome_arquivo}: brilho={brilho}, ruido={ruido}")

    except Exception as e:
        print(f"Erro em {nome_arquivo}: {e}")

print("Preprocessamento de imagens realizado.")