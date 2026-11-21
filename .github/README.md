# 逐帧复刻剪辑 · replicate-video-edit

用于按参考片重建剪辑与动效包装，交付分层工程，以及把原片和复刻片载入网页逐帧比较。

## 使用 Skill

下载 Release 中的 `replicate-video-edit.zip`，解压后将整个 `replicate-video-edit` 文件夹放进 `~/.codex/skills/`。在 Codex 中可以这样调用：

> 用 $replicate-video-edit 复刻这条视频的包装。A-roll 换成简笔人物，保留 B-roll 和包装音效。把原片和复刻片放在网页里同步比较，听左侧原声。

## 单独生成网页对照

需要 Python 3 和 ffprobe。在仓库根目录运行：

```sh
python3 scripts/make_review.py 原片.mp4 复刻.mp4 网页对照 \
  --cut-title "简笔复刻" --audio left --captions 口播.srt
```

打开输出目录中的 `左右对照.html`。两条视频已随页面放好，可同步播放、单帧步进、按段跳转或叠加查看。字幕文件可省略，已有剪点映射时可用 `--segments` 传入。

[Skill 完整说明](../SKILL.md) · [软件与分工](../references/packaging.md) · [网页对照流程](../references/web-review.md)
