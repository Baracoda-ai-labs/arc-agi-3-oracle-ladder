"""Test vide de T0.3 : le paquet et ses sous-modules s'importent."""
import importlib


def test_import_sous_modules():
    for m in ["world", "verify", "memory", "policy", "train", "eval", "registry"]:
        importlib.import_module(f"chrysalide.{m}")
