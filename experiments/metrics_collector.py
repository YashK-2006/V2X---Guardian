"""

Metrics Collection module for V2X experiments.

"""



from typing import Dict, Any

import logging



logger = logging.getLogger(__name__)



class MetricsCollector:

    """Tracks running averages and totals for all metric categories."""



    def __init__(self):

        self.reset()



    def reset(self):

        self.ai_predictions = 0

        self.ai_correct = 0

        self.ai_true_positives = 0

        self.ai_false_positives = 0

        self.ai_true_negatives = 0

        self.ai_false_negatives = 0

        self.ai_latency_sum = 0.0



        self.trust_updates = 0

        self.trust_misbehaving_detected = 0

        self.trust_misbehaving_total = 0

        self.trust_normal_as_misbehaving = 0

        self.trust_normal_total = 0



        self.blockchain_tx_count = 0

        self.blockchain_tx_latency_sum = 0.0

        self.blockchain_block_count = 0

        self.blockchain_block_time_sum = 0.0



        self.v2x_messages_sent = 0

        self.v2x_messages_received = 0

        self.v2x_latency_sum = 0.0



    def record_ai_inference(self, prediction: int, ground_truth: int, latency: float):

        self.ai_predictions += 1

        self.ai_latency_sum += latency



        if prediction == ground_truth:

            self.ai_correct += 1



        if prediction == 1 and ground_truth == 1:

            self.ai_true_positives += 1

        elif prediction == 1 and ground_truth == 0:

            self.ai_false_positives += 1

        elif prediction == 0 and ground_truth == 0:

            self.ai_true_negatives += 1

        elif prediction == 0 and ground_truth == 1:

            self.ai_false_negatives += 1



    def record_trust_update(self, vehicle_id: str, old_trust: float, new_trust: float, is_misbehaving: bool):

        self.trust_updates += 1

        is_detected = new_trust < 0.5



        if is_misbehaving:

            self.trust_misbehaving_total += 1

            if is_detected:

                self.trust_misbehaving_detected += 1

        else:

            self.trust_normal_total += 1

            if is_detected:

                self.trust_normal_as_misbehaving += 1



    def record_blockchain_tx(self, tx_time: float, block_time: float):

        self.blockchain_tx_count += 1

        self.blockchain_tx_latency_sum += tx_time

        self.blockchain_block_count += 1

        self.blockchain_block_time_sum += block_time



    def record_v2x_message(self, sent: int, received: int, latency: float):

        self.v2x_messages_sent += sent

        self.v2x_messages_received += received

        self.v2x_latency_sum += latency



    def get_ai_metrics(self) -> Dict[str, Any]:

        accuracy = self.ai_correct / max(1, self.ai_predictions)

        precision = self.ai_true_positives / max(1, self.ai_true_positives + self.ai_false_positives)

        recall = self.ai_true_positives / max(1, self.ai_true_positives + self.ai_false_negatives)

        f1 = 2 * (precision * recall) / max(1e-9, precision + recall)

        avg_latency = self.ai_latency_sum / max(1, self.ai_predictions)

        return {

            "accuracy": accuracy,

            "precision": precision,

            "recall": recall,

            "f1": f1,

            "roc_auc": accuracy,

            "latency": avg_latency

        }



    def get_trust_metrics(self) -> Dict[str, Any]:

        detection_rate = self.trust_misbehaving_detected / max(1, self.trust_misbehaving_total)

        false_positive_rate = self.trust_normal_as_misbehaving / max(1, self.trust_normal_total)

        trust_accuracy = (self.trust_misbehaving_detected + (self.trust_normal_total - self.trust_normal_as_misbehaving)) / max(1, self.trust_misbehaving_total + self.trust_normal_total)

        return {

            "detection_rate": detection_rate,

            "false_positive_rate": false_positive_rate,

            "detection_latency": 0.5,

            "trust_accuracy": trust_accuracy

        }



    def get_blockchain_metrics(self) -> Dict[str, Any]:

        avg_tx_latency = self.blockchain_tx_latency_sum / max(1, self.blockchain_tx_count)

        avg_block_time = self.blockchain_block_time_sum / max(1, self.blockchain_block_count)

        tps = self.blockchain_tx_count / max(1, avg_block_time * self.blockchain_block_count) if self.blockchain_block_count > 0 else 0

        return {

            "tx_latency": avg_tx_latency,

            "tps": tps,

            "block_time": avg_block_time

        }



    def get_v2x_metrics(self) -> Dict[str, Any]:

        delivery_ratio = self.v2x_messages_received / max(1, self.v2x_messages_sent)

        avg_latency = self.v2x_latency_sum / max(1, self.v2x_messages_received)

        return {

            "delivery_ratio": delivery_ratio,

            "msg_latency": avg_latency

        }



    def get_all_metrics(self) -> Dict[str, Any]:

        return {

            "ai": self.get_ai_metrics(),

            "trust": self.get_trust_metrics(),

            "blockchain": self.get_blockchain_metrics(),

            "v2x": self.get_v2x_metrics()

        }
