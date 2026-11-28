"""Métricas de detecção: AP no estilo COCO e qualidade dos pseudo-rótulos."""

import numpy as np
import torch
from torchvision.ops import box_iou


def average_precision(predictions: list[dict], ground_truths: list[np.ndarray], iou_threshold: float) -> float:
    """AP (interpolação em todos os pontos) para uma única classe."""
    records = []
    total_gt = sum(len(gt) for gt in ground_truths)
    if total_gt == 0:
        return float("nan")

    for prediction, gt in zip(predictions, ground_truths):
        boxes = prediction["boxes"].cpu()
        scores = prediction["scores"].cpu()
        order = scores.argsort(descending=True)
        matched = np.zeros(len(gt), dtype=bool)
        iou = box_iou(boxes[order], torch.as_tensor(gt)) if len(gt) and len(boxes) else None
        for rank, index in enumerate(order):
            true_positive = False
            if iou is not None:
                candidates = iou[rank].clone()
                candidates[torch.as_tensor(matched)] = -1
                best = int(candidates.argmax())
                if candidates[best] >= iou_threshold:
                    matched[best] = True
                    true_positive = True
            records.append((float(scores[index]), true_positive))

    if not records:
        return 0.0

    records.sort(key=lambda r: -r[0])
    hits = np.array([r[1] for r in records], dtype=np.float64)
    tp = np.cumsum(hits)
    fp = np.cumsum(1 - hits)
    recall = tp / total_gt
    precision = tp / np.maximum(tp + fp, 1e-9)

    recall = np.concatenate([[0.0], recall, [1.0]])
    precision = np.concatenate([[1.0], precision, [0.0]])
    precision = np.maximum.accumulate(precision[::-1])[::-1]
    steps = np.where(recall[1:] != recall[:-1])[0]
    return float(np.sum((recall[steps + 1] - recall[steps]) * precision[steps + 1]))


def evaluate(predictions: list[dict], ground_truths: list[np.ndarray], score_threshold: float) -> dict:
    """AP50, AP50:95, IoU médio e a qualidade que os pseudo-rótulos teriam neste limiar."""
    ap50 = average_precision(predictions, ground_truths, 0.5)
    ap = float(np.nanmean([
        average_precision(predictions, ground_truths, t) for t in np.arange(0.5, 0.96, 0.05)
    ]))

    best_ious = []
    accepted = correct = positives_found = negatives = false_alarms = 0
    for prediction, gt in zip(predictions, ground_truths):
        keep = prediction["scores"].cpu() >= score_threshold
        boxes = prediction["boxes"].cpu()[keep]
        if len(gt) == 0:
            negatives += 1
            false_alarms += int(len(boxes) > 0)
            continue

        gt_tensor = torch.as_tensor(gt)
        if len(prediction["boxes"]):
            # IoU da caixa de maior score com o melhor GT, independente do limiar
            top = prediction["boxes"].cpu()[prediction["scores"].cpu().argmax()].unsqueeze(0)
            best_ious.append(float(box_iou(top, gt_tensor).max()))
        else:
            best_ious.append(0.0)

        if len(boxes):
            iou = box_iou(boxes, gt_tensor)
            accepted += len(boxes)
            correct += int((iou.max(dim=1).values >= 0.5).sum())
            positives_found += int((iou.max(dim=0).values >= 0.5).sum())

    total_gt = sum(len(gt) for gt in ground_truths)
    return {
        "ap50": ap50,
        "ap50_95": ap,
        "mean_iou_top1": float(np.mean(best_ious)) if best_ious else float("nan"),
        "precision_at_threshold": correct / accepted if accepted else float("nan"),
        "recall_at_threshold": positives_found / total_gt if total_gt else float("nan"),
        "false_alarm_rate_negatives": false_alarms / negatives if negatives else float("nan"),
    }
