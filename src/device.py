"""Escolha do device (CPU ou GPU) dos pipelines, num lugar só.

Para forçar a CPU, use `--device cpu`. Não esconda a GPU com CUDA_VISIBLE_DEVICES=-1:
com torch 2.14 + CUDA 13 no Windows, `torch.cuda.is_available()` derruba o processo
(access violation, código 3221225477) quando nenhuma GPU está visível.
"""

import argparse

import torch

DEVICE_CHOICES = ("auto", "cpu", "cuda")


def add_device_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--device",
        choices=DEVICE_CHOICES,
        default="auto",
        help="auto usa a GPU se houver; cpu dá o mesmo resultado em qualquer máquina",
    )


def resolve_device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if name == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda pedido, mas nenhuma GPU CUDA está disponível.")
    return torch.device(name)
