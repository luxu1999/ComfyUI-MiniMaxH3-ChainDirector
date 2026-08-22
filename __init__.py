import torch

class ListToAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"audios": ("AUDIO",)}}

    INPUT_IS_LIST = True
    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "unwrap"
    CATEGORY = "utils"

    def unwrap(self, audios):
        if not audios:
            return ({"waveform": torch.zeros(1, 1, 0), "sample_rate": 16000},)
        return (audios[0],)


class ConcatImageBatches:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images_A": ("IMAGE",), "images_B": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "concat"
    CATEGORY = "utils"

    def concat(self, images_A, images_B):
        return (torch.cat([images_A, images_B], dim=0),)


NODE_CLASS_MAPPINGS = {
    "ListToAudio": ListToAudio,
    "ConcatImageBatches": ConcatImageBatches,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ListToAudio": "List To Audio",
    "ConcatImageBatches": "Concat Image Batches",
}

from .chain import MiniMaxH3ChainDirector  # noqa: E402
from .chain_en import MiniMaxH3ChainDirectorEN  # noqa: E402

NODE_CLASS_MAPPINGS["MiniMaxH3ChainDirector"] = MiniMaxH3ChainDirector
NODE_DISPLAY_NAME_MAPPINGS["MiniMaxH3ChainDirector"] = "MiniMax H3 Chain Director｜链式导演台（多段拼接）"
NODE_CLASS_MAPPINGS["MiniMaxH3ChainDirectorEN"] = MiniMaxH3ChainDirectorEN
NODE_DISPLAY_NAME_MAPPINGS["MiniMaxH3ChainDirectorEN"] = "MiniMax H3 Chain Director"