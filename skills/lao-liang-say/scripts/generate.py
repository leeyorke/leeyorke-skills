#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老梁说 - 生成脚本
用于以老梁风格生成文章/演讲稿/短视频脚本
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# 添加 references 到路径
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
REF_DIR = SKILL_DIR / "references"


class LaoLiangGenerator:
    """老梁风格生成器"""

    def __init__(self):
        self.style_guide = self._load_reference("style-guide.md")
        self.openings = self._load_reference("openings.md")
        self.closings = self._load_reference("closings.md")
        self.phrases = self._load_reference("phrases.md")
        self.structures = self._load_reference("structures.md")

    def _load_reference(self, filename: str) -> str:
        path = REF_DIR / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def build_system_prompt(self) -> str:
        """构建系统提示词"""
        return f"""你是老梁（梁宏达），要以老梁的风格写文章/演讲稿/短视频脚本。

## 核心人设
- 平民视角的说书人：用评书相声的法子"说书讲事儿"
- 敢下判断的时评人：观点犀利笃定，不留商量余地
- 雅俗共赏的段子手：半文半白，引经据典又接地气

## 语气四层切换（必须体现）
1. 和风细雨聊天感（开场、铺陈）——像邻居大哥掰扯
2. 犀利笃定判断感（亮观点、戳破假象）——语速加快、重音砸下
3. 幽默调侃松弛感（穿插段子、吐槽、自嘲）——裹层糖衣
4. 语重心长收束感（结尾升华）——放慢、压低、回到"人"的层面

## 结构：凤头·猪肚·豹尾
- 凤头：标准问候+直入主题，三句话内抛钩子（反常/热点/人物）
- 猪肚：讲一段、评一段交替；剥洋葱四层（现象→背景→人性/利益→升华）；旁支斜出穿插历史八卦
- 豹尾：收网(点主线)→升华(上普遍)→诗词/金句点睛→人情道别

## 高频口语标记（全文覆盖）
咱说/你看啊/说白了/归根到底/这里头有门道/话又说回来/这就好比/老话讲得好/你猜怎么着/咱们大伙琢磨琢磨

## 禁忌
❌ 首先其次最后等书面连接词 ❌ 开场寒暄预告 ❌ 观点模棱两可 ❌ 结尾堆料喊口号 ❌ 人身攻击

## 参考资料（内化为直觉，不直接引用）
{self.style_guide[:3000]}
{self.openings[:2000]}
{self.closings[:2000]}
{self.phrases[:2000]}
{self.structures[:3000]}
"""

    def build_user_prompt(self, topic: str, format_type: str = "article",
                          audience: str = "大众", length: str = "中等",
                          angle: Optional[str] = None) -> str:
        """构建用户提示词"""
        format_map = {
            "article": "公众号深度文章（2500-4000字）",
            "speech": "演讲稿（15-20分钟，3000-4000字）",
            "video": "短视频脚本（60-90秒，500-800字）",
            "post": "朋友圈/短文案（300-500字）"
        }

        prompt = f"""主题：{topic}
格式：{format_map.get(format_type, format_type)}
目标受众：{audience}
篇幅偏好：{length}"""

        if angle:
            prompt += f"\n切入角度：{angle}"

        prompt += """

请输出完整稿件，包含：
1. 标题（有反差/悬念/金句感）
2. 正文（严格按老梁结构、语气、口语、禁忌执行）
3. 无需额外解释、无需元数据、直接给稿件"""

        return prompt

    def generate(self, topic: str, format_type: str = "article",
                 audience: str = "大众", length: str = "中等",
                 angle: Optional[str] = None) -> Dict[str, str]:
        """生成提示词包（供 LLM 使用）"""
        return {
            "system": self.build_system_prompt(),
            "user": self.build_user_prompt(topic, format_type, audience, length, angle),
            "meta": {
                "topic": topic,
                "format": format_type,
                "audience": audience,
                "length": length,
                "angle": angle
            }
        }


def main():
    parser = argparse.ArgumentParser(description="老梁说 - 生成老梁风格稿件提示词")
    parser.add_argument("topic", help="主题/核心观点")
    parser.add_argument("-f", "--format", choices=["article", "speech", "video", "post"],
                        default="article", help="输出格式")
    parser.add_argument("-a", "--audience", default="大众", help="目标受众")
    parser.add_argument("-l", "--length", choices=["短", "中等", "长"], default="中等", help="篇幅")
    parser.add_argument("--angle", help="切入角度/特定要求")
    parser.add_argument("-o", "--output", help="输出文件路径（JSON）")
    parser.add_argument("--prompt-only", action="store_true", help="仅输出提示词，不调用模型")

    args = parser.parse_args()

    generator = LaoLiangGenerator()
    prompt_pack = generator.generate(
        topic=args.topic,
        format_type=args.format,
        audience=args.audience,
        length=args.length,
        angle=args.angle
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(prompt_pack, f, ensure_ascii=False, indent=2)
        print(f"提示词包已保存至：{args.output}")
    else:
        print(json.dumps(prompt_pack, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()