import numpy as np
import PIL.Image

def image2matrix(image) -> np.array:
    """
    Função para converter uma imagem em uma matriz NumPy. A imagem é aberta usando a biblioteca PIL, 
    convertida para escala de cinza e, em seguida, transformada em um array NumPy.
    """

    image = PIL.Image.open(image)
    gray_image = image.convert("L")

    return np.array(gray_image)