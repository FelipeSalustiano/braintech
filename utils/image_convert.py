import numpy as np
import PIL.Image
import torch

def image2matrix(image) -> np.array:
    """
    Função para converter uma imagem em uma matriz NumPy.
    """

    image = PIL.Image.open(image)
    gray_image = image.convert("L")

    return np.array(gray_image)


def image2tensor(image, npArray=False, n_dim=None) -> torch.Tensor:
    """
    Função para converter uma imagem em um tensor NumPy.
    """

    if npArray:
        tensor = torch.from_numpy(image).float()

    else:
        image = image2matrix(image)
        tensor = torch.from_numpy(image).float()

    if n_dim is not None:
        for _ in range(n_dim - tensor.ndim):
            tensor = tensor.unsqueeze(0)

    return tensor