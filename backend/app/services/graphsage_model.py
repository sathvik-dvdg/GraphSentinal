# [WSL2]
import torch
from torch import nn
from torch.nn import functional as F


class GraphSAGEClassifier(nn.Module):
    def __init__(
        self,
        in_channels: int = 7,
        hidden_channels: int = 256,
        out_channels: int = 2,
        num_layers: int = 3,
        dropout: float = 0.3,
        aggr: str = "mean",
    ):
        super().__init__()
        try:
            from torch_geometric.nn import SAGEConv
        except Exception as exc:
            raise RuntimeError("torch_geometric is required for GraphSAGE weights") from exc

        if num_layers != 3:
            raise ValueError("Saved GraphSentinel weights expect exactly 3 layers")

        self.dropout = dropout
        self.convs = nn.ModuleList(
            [
                SAGEConv(in_channels, hidden_channels, aggr=aggr),
                SAGEConv(hidden_channels, hidden_channels, aggr=aggr),
                SAGEConv(hidden_channels, out_channels, aggr=aggr),
            ]
        )
        self.bns = nn.ModuleList(
            [
                nn.BatchNorm1d(hidden_channels),
                nn.BatchNorm1d(hidden_channels),
            ]
        )

    def forward(self, x, edge_index):
        for index, conv in enumerate(self.convs[:-1]):
            x = conv(x, edge_index)
            x = self.bns[index](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        return self.convs[-1](x, edge_index)

    def predict_proba(self, x, edge_index):
        logits = self.forward(x, edge_index)
        return torch.softmax(logits, dim=1)[:, 1]

