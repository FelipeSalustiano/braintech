import numpy as np
import cv2
from utils.image_convert import image2matrix


class ImageAnalyzer:
    """
    Classe para analisar imagens, fornecendo métodos para calcular brilho e ruído, 
    bem como determinar o status de brilho e ruído com base em limites definidos.
    """

    def __init__(self, image):
        self.image = image2matrix(image)


    def get_brightness(self, image=None):
        img = image if image is not None else self.image
        return np.mean(img)


    def get_noise(self, image=None):
        img = image if image is not None else self.image
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        return laplacian.var()


    def brightness_status(self, image=None, low=60, high=200):
        brightness = self.get_brightness(image)
        if brightness > high:
            return "clara"
        elif brightness < low:
            return "escura"
        return "ok"


    def noise_status(self, image=None, low=70, high=130):
        variance = self.get_noise(image)
        if variance < low:
            return "borrada"   
        elif variance > high:
            return "ruidosa"   
        return "ok"


class Filter:
    """
    Classe para aplicar filtros em imagens, incluindo suavização, nitidez, 
    ajuste de brilho e contraste.
    """

    def __init__(self, image):
        self.image = image2matrix(image)
        

    def suavization(self, x_matrix=5, y_matrix=5) -> np.array:
        self.image = cv2.GaussianBlur(self.image, (x_matrix, y_matrix), 0)
        return self.image


    def sharpen(self, strength: float=1.0) -> np.array:
        blurred = cv2.GaussianBlur(self.image, (0, 0), sigmaX=3)
        self.image = cv2.addWeighted(self.image, 1 + strength, blurred, -strength, 0)
        return self.image

    
    def increase_brightness(self, value: int=50) -> np.array:
        self.image = cv2.convertScaleAbs(self.image, alpha=1.0, beta=value)
        return self.image


    def decrease_brightness(self, value: int=50) -> np.array:
        self.image = cv2.convertScaleAbs(self.image, alpha=1.0, beta=-value)
        return self.image


    def contrast_stretch(self) -> np.array:
        img = self.image.astype(np.float32)
        min_val, max_val = img.min(), img.max()

        if max_val - min_val == 0:
            return self.image

        stretched = (img - min_val) * (255.0 / (max_val - min_val))
        self.image = stretched.astype(np.uint8)
        return self.image