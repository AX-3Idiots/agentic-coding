"""
Constants for AWS Foundation Models and Inference Profiles available in us-east-1 region.
"""

from enum import Enum

class AWSModel(str, Enum):
    """
    AWS Foundation Models and Inference Profiles available in us-east-1 region.
    """
    # Foundation Models
    ANTHROPIC_CLAUDE_3_SONNET = "anthropic.claude-3-sonnet-20240229-v1:0"
    ANTHROPIC_CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
    ANTHROPIC_CLAUDE_2_1 = "anthropic.claude-2.1"
    ANTHROPIC_CLAUDE_INSTANT = "anthropic.claude-instant-v1"
    META_LLAMA_2_70B = "meta.llama2.70b-chat-v1"
    META_LLAMA_2_13B = "meta.llama2.13b-chat-v1"
    META_LLAMA_2_7B = "meta.llama2.7b-chat-v1"
    MISTRAL_7B = "mistral.mistral-7b-instruct-v0:2"
    MISTRAL_MIXTRAL = "mistral.mixtral-8x7b-instruct-v0:1"
    AMAZON_TITAN_LARGE = "amazon.titan-text-express-v1"
    AMAZON_TITAN_LITE = "amazon.titan-text-lite-v1"
    COHERE_COMMAND = "cohere.command-text-v14"
    COHERE_COMMAND_LIGHT = "cohere.command-light-text-v14"
    STABILITY_STABLE_DIFFUSION = "stability.stable-diffusion-xl-v1"
    STABILITY_STABLE_DIFFUSION_LITE = "stability.stable-diffusion-xl-lite-v1"

    # Cross-Region Inference Profiles
    ANTHROPIC_CLAUDE_4_SONNET_CROSS_REGION = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    ANTHROPIC_CLAUDE_3_SONNET_CROSS_REGION = "us.anthropic.claude-3-sonnet-20240229-v1:0-cross-region"
    ANTHROPIC_CLAUDE_3_HAIKU_CROSS_REGION = "us.anthropic.claude-3-haiku-20240307-v1:0-cross-region"
    ANTHROPIC_CLAUDE_2_1_CROSS_REGION = "us.anthropic.claude-2.1-cross-region"
    ANTHROPIC_CLAUDE_INSTANT_CROSS_REGION = "us.anthropic.claude-instant-v1-cross-region"
    ANTHROPIC_CLAUDE_3_7_SONNET_CROSS_REGION = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    META_LLAMA4_SCOUT_17B_INSTRUCT_CROSS_REGION = "us.meta.llama4-scout-17b-instruct-v1:0"
    META_LLAMA4_MAVERICK_17B_INSTRUCT_CROSS_REGION = "us.meta.llama4-maverick-17b-instruct-v1:0"
    META_LLAMA3_3_70B_CROSS_REGION = "us.meta.llama3-3-70b-instruct-v1:0"
    META_LLAMA3_3_13B_CROSS_REGION = "us.meta.llama3-3-13b-instruct-v1:0"
    META_LLAMA_2_7B_CROSS_REGION = "us.meta.llama2.7b-chat-v1-cross-region"
    MISTRAL_7B_CROSS_REGION = "us.mistral.mistral-7b-instruct-v0:2-cross-region"
    MISTRAL_MIXTRAL_CROSS_REGION = "us.mistral.mixtral-8x7b-instruct-v0:1-cross-region"
    AMAZON_TITAN_LARGE_CROSS_REGION = "us.amazon.titan-text-express-v1-cross-region"
    AMAZON_TITAN_LITE_CROSS_REGION = "us.amazon.titan-text-lite-v1-cross-region"
    COHERE_COMMAND_CROSS_REGION = "us.cohere.command-text-v14-cross-region"
    COHERE_COMMAND_LIGHT_CROSS_REGION = "us.cohere.command-light-text-v14-cross-region"
    STABILITY_STABLE_DIFFUSION_CROSS_REGION = "us.stability.stable-diffusion-xl-v1-cross-region"
    STABILITY_STABLE_DIFFUSION_LITE_CROSS_REGION = "us.stability.stable-diffusion-xl-lite-v1-cross-region"
    ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION = "apac.anthropic.claude-sonnet-4-20250514-v1:0"



    @classmethod
    def get_text_models(cls):
        """Get all text models"""
        return [
            cls.ANTHROPIC_CLAUDE_3_SONNET,
            cls.ANTHROPIC_CLAUDE_3_HAIKU,
            cls.ANTHROPIC_CLAUDE_2_1,
            cls.ANTHROPIC_CLAUDE_INSTANT,
            cls.META_LLAMA_2_70B,
            cls.META_LLAMA_2_13B,
            cls.META_LLAMA_2_7B,
            cls.MISTRAL_7B,
            cls.MISTRAL_MIXTRAL,
            cls.AMAZON_TITAN_LARGE,
            cls.AMAZON_TITAN_LITE,
            cls.COHERE_COMMAND,
            cls.COHERE_COMMAND_LIGHT,
            cls.ANTHROPIC_CLAUDE_3_SONNET_CROSS_REGION,
            cls.ANTHROPIC_CLAUDE_3_HAIKU_CROSS_REGION,
            cls.ANTHROPIC_CLAUDE_2_1_CROSS_REGION,
            cls.ANTHROPIC_CLAUDE_INSTANT_CROSS_REGION,
            cls.META_LLAMA4_SCOUT_17B_INSTRUCT_CROSS_REGION,
            cls.META_LLAMA4_MAVERICK_17B_INSTRUCT_CROSS_REGION,
            cls.META_LLAMA3_3_70B_CROSS_REGION,
            cls.META_LLAMA3_3_13B_CROSS_REGION,
            cls.META_LLAMA_2_7B_CROSS_REGION,
            cls.MISTRAL_7B_CROSS_REGION,
            cls.MISTRAL_MIXTRAL_CROSS_REGION,
            cls.AMAZON_TITAN_LARGE_CROSS_REGION,
            cls.AMAZON_TITAN_LITE_CROSS_REGION,
            cls.COHERE_COMMAND_CROSS_REGION,
            cls.COHERE_COMMAND_LIGHT_CROSS_REGION,
            cls.ANTHROPIC_CLAUDE_4_SONNET_CROSS_REGION,
            cls.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION
        ]

    @classmethod
    def get_image_models(cls):
        """Get all image models"""
        return [
            cls.STABILITY_STABLE_DIFFUSION,
            cls.STABILITY_STABLE_DIFFUSION_LITE,
        ]

    @classmethod
    def get_all_models(cls):
        """Get all available models"""
        return cls.get_text_models() + cls.get_image_models()
