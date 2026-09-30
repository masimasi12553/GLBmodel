# GLBmodel

ボクセル調キャラクターの GLB モデル集。

## villagers/

heroine.glb と同じ作りの村人 7 体（1ボクセル = 0.026m、スキンメッシュ1つ＋パレットテクスチャ1枚）。

| ファイル | キャラクター |
|---|---|
| villager.glb | 青年（ベスト・ネッカチーフ） |
| villager_man_a.glb | ひげの中年男性（ベスト・スカーフ） |
| villager_man_b.glb | 職人（ハンチング帽・革エプロン） |
| villager_child_a.glb | 男の子（黄色いチュニック） |
| villager_child_b.glb | 女の子（ツインテール・エプロンドレス） |
| villager_woman_a.glb | 女性（お団子髪・赤いドレス） |
| villager_woman_b.glb | 女性（スカーフ・三つ編み） |

ボーン: Root / Hips / Spine / Chest / Neck / Head / {L,R}UpperArm / LowerArm / Hand / Thigh / Shin / Foot
（child_b は {L,R}Tail1-2、woman_b は Braid1-2 を追加）

アニメーション: Idle, Walk, Run, Wave, Nod, ShakeHead, Bow, Talk, Joy, Surprise, Sad, Hurt

再生成: `pip install numpy pillow && python3 tools/villagers.py`
