import json
import os

import torch
from torch.utils.data import Dataset
from PIL import Image
from torchvision import transforms


class MeterDataset(Dataset):

    def __init__(
        self,
        json_path,
        image_dir,
        image_ids=None
    ):

        self.image_dir = image_dir

        # Carrega JSON
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        # Informações das imagens
        self.images = {
            img["id"]: img
            for img in self.data["images"]
        }

        # Agrupa anotações por imagem
        self.annotations = {}

        for annotation in self.data["annotations"]:

            image_id = annotation["image_id"]

            if image_id not in self.annotations:
                self.annotations[image_id] = []

            self.annotations[image_id].append(annotation)

        # Usa somente imagens que possuem anotação
        valid_ids = [
            image_id
            for image_id in self.images
            if image_id in self.annotations
        ]

        if image_ids is not None:
            valid_ids = [
                image_id
                for image_id in valid_ids
                if image_id in image_ids
            ]

        self.image_ids = valid_ids

        # Transformação
        self.transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.ToTensor()
        ])

        # Dimensão da grade produzida pela rede
        self.grid_h = 60
        self.grid_w = 45

    def __len__(self):

        return len(self.image_ids)

    def __getitem__(self, index):

        image_id = self.image_ids[index]

        image_info = self.images[image_id]

        filename = image_info["file_name"]

        image_path = os.path.join(
            self.image_dir,
            filename
        )

        # Abre imagem
        image = Image.open(image_path).convert("RGB")

        image_width = image_info["width"]
        image_height = image_info["height"]

        # Converte para tensor
        image = self.transform(image)

        # Target
        target = torch.zeros(
            5,
            self.grid_h,
            self.grid_w,
            dtype=torch.float32
        )

        annotations = self.annotations[image_id]

        for annotation in annotations:

            x, y, w, h = annotation["bbox"]

            # Centro da bounding box
            center_x = x + w / 2
            center_y = y + h / 2

            # Normalização
            center_x_norm = center_x / image_width
            center_y_norm = center_y / image_height

            width_norm = w / image_width
            height_norm = h / image_height

            # Descobre a célula da grade
            grid_x = int(
                center_x_norm * self.grid_w
            )

            grid_y = int(
                center_y_norm * self.grid_h
            )

            # Proteção
            grid_x = min(
                max(grid_x, 0),
                self.grid_w - 1
            )

            grid_y = min(
                max(grid_y, 0),
                self.grid_h - 1
            )

            # Coordenada relativa dentro da célula
            local_x = (
                center_x_norm * self.grid_w
                - grid_x
            )

            local_y = (
                center_y_norm * self.grid_h
                - grid_y
            )

            # Salva target
            target[0, grid_y, grid_x] = local_x
            target[1, grid_y, grid_x] = local_y
            target[2, grid_y, grid_x] = width_norm
            target[3, grid_y, grid_x] = height_norm

            # Existe objeto nessa célula
            target[4, grid_y, grid_x] = 1.0

        return image, target