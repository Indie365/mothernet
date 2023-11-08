from math import pi, log
from functools import wraps

import torch
from torch import nn, einsum
import torch.nn.functional as F

from einops import rearrange, repeat
from einops.layers.torch import Reduce

from tabpfn.decoders import MLPModelDecoder
from tabpfn.transformer_make_model import MLPModelPredictor

# helpers

def exists(val):
    return val is not None

def default(val, d):
    return val if exists(val) else d

# def cache_fn(f):
#     cache = dict()
#     @wraps(f)
#     def cached_fn(*args, _cache = True, key = None, **kwargs):
#         if not _cache:
#             return f(*args, **kwargs)
#         nonlocal cache
#         if key in cache:
#             return cache[key]
#         result = f(*args, **kwargs)
#         cache[key] = result
#         return result
#     return cached_fn

def fourier_encode(x, max_freq, num_bands = 4):
    x = x.unsqueeze(-1)
    device, dtype, orig_x = x.device, x.dtype, x

    scales = torch.linspace(1., max_freq / 2, num_bands, device = device, dtype = dtype)
    scales = scales[(*((None,) * (len(x.shape) - 1)), Ellipsis)]

    x = x * scales * pi
    x = torch.cat([x.sin(), x.cos()], dim = -1)
    x = torch.cat((x, orig_x), dim = -1)
    return x

# helper classes

class PreNorm(nn.Module):
    def __init__(self, dim, fn, context_dim = None):
        super().__init__()
        self.fn = fn
        self.norm = nn.LayerNorm(dim)
        self.norm_context = nn.LayerNorm(context_dim) if exists(context_dim) else None

    def forward(self, x, **kwargs):
        x = self.norm(x)

        if exists(self.norm_context):
            context = kwargs['context']
            normed_context = self.norm_context(context)
            kwargs.update(context = normed_context)

        return self.fn(x, **kwargs)

class GEGLU(nn.Module):
    def forward(self, x):
        x, gates = x.chunk(2, dim = -1)
        return x * F.gelu(gates)

class FeedForward(nn.Module):
    def __init__(self, dim, mult = 4, dropout = 0.):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim * mult * 2),
            GEGLU(),
            nn.Linear(dim * mult, dim),
            nn.Dropout(dropout)
        )

    def forward(self, x):
        return self.net(x)

class Attention(nn.Module):
    def __init__(self, query_dim, context_dim = None, heads = 8, dim_head = 64, dropout = 0.):
        super().__init__()
        inner_dim = dim_head * heads
        context_dim = default(context_dim, query_dim)

        self.scale = dim_head ** -0.5
        self.heads = heads

        self.to_q = nn.Linear(query_dim, inner_dim, bias = False)
        self.to_kv = nn.Linear(context_dim, inner_dim * 2, bias = False)

        self.dropout = nn.Dropout(dropout)
        self.to_out = nn.Linear(inner_dim, query_dim)

    def forward(self, x, context = None, mask = None):
        h = self.heads

        q = self.to_q(x)
        context = default(context, x)
        k, v = self.to_kv(context).chunk(2, dim = -1)

        q, k, v = map(lambda t: rearrange(t, 'b n (h d) -> (b h) n d', h = h), (q, k, v))

        sim = einsum('b i d, b j d -> b i j', q, k) * self.scale

        if exists(mask):
            mask = rearrange(mask, 'b ... -> b (...)')
            max_neg_value = -torch.finfo(sim.dtype).max
            mask = repeat(mask, 'b j -> (b h) () j', h = h)
            sim.masked_fill_(~mask, max_neg_value)

        # attention, what we cannot get enough of
        attn = sim.softmax(dim = -1)
        attn = self.dropout(attn)

        out = einsum('b i j, b j d -> b i d', attn, v)
        out = rearrange(out, '(b h) n d -> b n (h d)', h = h)
        return self.to_out(out)

# main class

class Perceiver(nn.Module):
    def __init__(
        self,
        *,
        num_freq_bands,
        depth,
        max_freq,
        input_channels = 3,
        input_axis = 2,
        num_latents = 512,
        latent_dim = 512,
        cross_heads = 1,
        latent_heads = 8,
        cross_dim_head = 64,
        latent_dim_head = 64,
        num_classes = 1000,
        attn_dropout = 0.,
        ff_dropout = 0.,
        weight_tie_layers = False,
        fourier_encode_data = True,
        self_per_cross_attn = 1,
        final_classifier_head = True
    ):
        """The shape of the final attention mechanism will be:
        depth * (cross attention -> self_per_cross_attn * self attention)

        Args:
          num_freq_bands: Number of freq bands, with original value (2 * K + 1)
          depth: Depth of net.
          max_freq: Maximum frequency, hyperparameter depending on how
              fine the data is.
          freq_base: Base for the frequency
          input_channels: Number of channels for each token of the input.
          input_axis: Number of axes for input data (2 for images, 3 for video)
          num_latents: Number of latents, or induced set points, or centroids.
              Different papers giving it different names.
          latent_dim: Latent dimension.
          cross_heads: Number of heads for cross attention. Paper said 1.
          latent_heads: Number of heads for latent self attention, 8.
          cross_dim_head: Number of dimensions per cross attention head.
          latent_dim_head: Number of dimensions per latent self attention head.
          num_classes: Output number of classes.
          attn_dropout: Attention dropout
          ff_dropout: Feedforward dropout
          weight_tie_layers: Whether to weight tie layers (optional).
          fourier_encode_data: Whether to auto-fourier encode the data, using
              the input_axis given. defaults to True, but can be turned off
              if you are fourier encoding the data yourself.
          self_per_cross_attn: Number of self attention blocks per cross attn.
          final_classifier_head: mean pool and project embeddings to number of classes (num_classes) at the end
        """
        super().__init__()
        self.input_axis = input_axis
        self.max_freq = max_freq
        self.num_freq_bands = num_freq_bands

        self.fourier_encode_data = fourier_encode_data
        fourier_channels = (input_axis * ((num_freq_bands * 2) + 1)) if fourier_encode_data else 0
        input_dim = fourier_channels + input_channels

        self.latents = nn.Parameter(torch.randn(num_latents, latent_dim))

        self.layers = nn.ModuleList([])
        for i in range(depth):
            should_cache = i > 0 and weight_tie_layers
            cache_args = {'_cache': should_cache}

            self_attns = nn.ModuleList([])

            for block_ind in range(self_per_cross_attn):
                self_attns.append(nn.ModuleList([
                    PreNorm(latent_dim, Attention(latent_dim, heads = latent_heads, dim_head = latent_dim_head, dropout = attn_dropout)),
                    PreNorm(latent_dim, FeedForward(latent_dim, dropout = ff_dropout, ))
                ]))

            self.layers.append(nn.ModuleList([
                PreNorm(latent_dim, Attention(latent_dim, input_dim, heads = cross_heads, dim_head = cross_dim_head, dropout = attn_dropout), context_dim = input_dim),
                PreNorm(latent_dim, FeedForward(latent_dim, dropout = ff_dropout)),
                self_attns
            ]))

        self.to_logits = nn.Sequential(
            Reduce('b n d -> b d', 'mean'),
            nn.LayerNorm(latent_dim),
            nn.Linear(latent_dim, num_classes)
        ) if final_classifier_head else nn.Identity()

    def forward(
        self,
        data,
        mask = None,
        return_embeddings = False
    ):
        b, *axis, _, device, dtype = *data.shape, data.device, data.dtype
        assert len(axis) == self.input_axis, 'input data must have the right number of axis'

        if self.fourier_encode_data:
            # calculate fourier encoded positions in the range of [-1, 1], for all axis

            axis_pos = list(map(lambda size: torch.linspace(-1., 1., steps=size, device=device, dtype=dtype), axis))
            pos = torch.stack(torch.meshgrid(*axis_pos, indexing = 'ij'), dim = -1)
            enc_pos = fourier_encode(pos, self.max_freq, self.num_freq_bands)
            enc_pos = rearrange(enc_pos, '... n d -> ... (n d)')
            enc_pos = repeat(enc_pos, '... -> b ...', b = b)

            data = torch.cat((data, enc_pos), dim = -1)

        # concat to channels of data and flatten axis

        data = rearrange(data, 'b ... d -> b (...) d')

        x = repeat(self.latents, 'n d -> b n d', b = b)

        # layers

        for cross_attn, cross_ff, self_attns in self.layers:
            x = cross_attn(x, context = data, mask = mask) + x
            x = cross_ff(x) + x

            for self_attn, self_ff in self_attns:
                x = self_attn(x) + x
                x = self_ff(x) + x

        # allow for fetching embeddings

        if return_embeddings:
            return x

        # to logits

        return self.to_logits(x)




class TabPerceiver(MLPModelPredictor):
    def __init__(
        self,
        *,
        depth,
        input_dim = 512,
        input_axis = 1,
        num_latents = 512,
        latent_dim = 512,
        cross_heads = 1,
        latent_heads = 8,
        cross_dim_head = 64,
        latent_dim_head = 64,
        n_out = 10,
        attn_dropout = 0.,
        ff_dropout = 0.,
        self_per_cross_attn = 1,
        decoder_hidden_size = 512,
        predicted_hidden_layer_size=128,
        output_attention=True,
        decoder_embed_dim=512,
        special_token=False,
        decoder_two_hidden_layers=False, no_double_embedding=False,
        y_encoder=None,
        encoder=None,
        predicted_hidden_layers=1,
        weight_embedding_rank=None
    ):
        """The shape of the final attention mechanism will be:
        depth * (cross attention -> self_per_cross_attn * self attention)

        Args:
          depth: Depth of net.
          input_channels: Number of channels for each token of the input.
          input_axis: Number of axes for input data (2 for images, 3 for video)
          num_latents: Number of latents, or induced set points, or centroids.
              Different papers giving it different names.
          latent_dim: Latent dimension.
          cross_heads: Number of heads for cross attention. Paper said 1.
          latent_heads: Number of heads for latent self attention, 8.
          cross_dim_head: Number of dimensions per cross attention head.
          latent_dim_head: Number of dimensions per latent self attention head.
          num_classes: Output number of classes.
          attn_dropout: Attention dropout
          ff_dropout: Feedforward dropout
          weight_tie_layers: Whether to weight tie layers (optional).

          self_per_cross_attn: Number of self attention blocks per cross attn.
          final_classifier_head: mean pool and project embeddings to number of classes (num_classes) at the end
        """
        super().__init__()
        self.y_encoder = y_encoder
        self.encoder = encoder
        self.input_axis = input_axis
        # input_dim is the input to the transformer, which is after the first linear embedding, so it's emsize
        self.input_dim = input_dim
        self.n_out = n_out
        assert not special_token
        self.special_token = special_token
        self.no_double_embedding = no_double_embedding
        self.latents = nn.Parameter(0.02 * torch.randn(num_latents, latent_dim))

        self.layers = nn.ModuleList([])
        for i in range(depth):
            self_attns = nn.ModuleList([])

            for block_ind in range(self_per_cross_attn):
                latent_block = nn.Module()
                latent_block.add_module('latent_attn', PreNorm(latent_dim, Attention(latent_dim, heads = latent_heads, dim_head = latent_dim_head, dropout = attn_dropout)))
                latent_block.add_module('latent_ff', PreNorm(latent_dim, FeedForward(latent_dim, dropout = ff_dropout, mult=1)))
                self_attns.append(latent_block)

            cross_attn_layer = nn.Module()
            cross_attn_layer.add_module('cross_attn', PreNorm(latent_dim, Attention(latent_dim, input_dim, heads = cross_heads, dim_head = cross_dim_head, dropout = attn_dropout), context_dim = input_dim))
            cross_attn_layer.add_module('cross_ff', PreNorm(latent_dim, FeedForward(latent_dim, dropout = ff_dropout, mult=1)))
            cross_attn_layer.add_module('latents', self_attns)
            self.layers.append(cross_attn_layer)
        self.decoder = MLPModelDecoder(emsize=latent_dim, hidden_size=decoder_hidden_size, n_out=n_out, output_attention=output_attention,
                                       special_token=special_token, predicted_hidden_layer_size=predicted_hidden_layer_size, embed_dim=decoder_embed_dim,
                                       decoder_two_hidden_layers=decoder_two_hidden_layers, no_double_embedding=no_double_embedding, nhead=latent_heads, predicted_hidden_layers=predicted_hidden_layers,
                                       weight_embedding_rank=weight_embedding_rank)

    def inner_forward(self, data):
        #b, *axis, _, device, dtype = *data.shape, data.device, data.dtype
        # assert len(axis) == self.input_axis, 'input data must have the right number of axis'
        assert len(data.shape) == self.input_axis + 2, 'input data must have the right number of axis'
        b = data.shape[1]
        # concat to channels of data and flatten axis
        # data = rearrange(data, 'b ... d -> b (...) d')

        x = repeat(self.latents, 'n d -> b n d', b = b)

        # attention is implemented with batch in first dimension
        data = rearrange(data, 'n b d -> b n d')

        # layers
        for layer in self.layers:
            x = layer.cross_attn(x, context = data) + x
            x = layer.cross_ff(x) + x

            for latent in layer.latents:
                x = latent.latent_attn(x) + x
                x = latent.latent_ff(x) + x

        x = rearrange(x, 'b n d -> n b d')
        return x

    # def forward(
    #     self,
    #     src,
    #     single_eval_pos=None,
    # ):
    #     assert isinstance(src, tuple), 'inputs (src) have to be given as (x,y)'
    #     _, x_src_org, y_src = src
    #     x_src = self.encoder(x_src_org)
    #     y_src = self.y_encoder(y_src.unsqueeze(-1) if len(y_src.shape) < len(x_src.shape) else y_src)
    #     data = x_src[:single_eval_pos] + y_src[:single_eval_pos]

    #     x = self.inner_forward(data)

    #     b1, w1, *layers = self.decoder(x)
    #     if self.no_double_embedding:
    #         x_src_org_nona = torch.nan_to_num(x_src_org[single_eval_pos:], nan=0)
    #         h1 = (x_src_org_nona.unsqueeze(-1) * w1.unsqueeze(0)).sum(2) + b1
    #     else:
    #         h1 = (x_src[single_eval_pos:].unsqueeze(-1) * w1.unsqueeze(0)).sum(2) + b1
    #     h1 = torch.relu(h1)
    #     result = (h1.unsqueeze(-1) * w2.unsqueeze(0)).sum(2) + b2
    #     if result.isnan().all():
    #         import pdb; pdb.set_trace()
    #     return result