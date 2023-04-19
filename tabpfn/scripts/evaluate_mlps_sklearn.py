from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.compose import make_column_transformer
from tabpfn.scripts.transformer_prediction_interface import TabPFNClassifier

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import make_column_transformer
from sklearn.model_selection import cross_validate
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier

from tabpfn.transformer_make_model import ForwardLinearModel


def make_mlp(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, TorchMLP(n_epochs=100))

def make_forward_linear_model(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, ForwardLinearModel())

def make_forward_mlp_model(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, ForwardMLPModel())

def make_forward_mlp_model_new(categorical_features):
    path = "models_diff/prior_diff_real_checkpoint_output_attention_nlayer6_mlp_emsize_512_multiclass_04_17_2023_23_11_02_n_0_epoch_94.cpkt"
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, ForwardMLPModel(path=path))

def make_forward_mlp_model_big_bugfix_caching(categorical_features):
    path_new_big = "models_diff/prior_diff_real_checkpoint_predict_mlp_attention_nlayer12_lr0001_multiclass_04_18_2023_21_31_58_n_0_epoch_40.cpkt"
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, ForwardMLPModel(path=path_new_big))


def make_forward_mlp_model_big_bugfix_caching_permutations(categorical_features):
    path_new_big = "models_diff/prior_diff_real_checkpoint_predict_mlp_attention_nlayer12_lr0001_multiclass_04_18_2023_21_31_58_n_0_epoch_40.cpkt"
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    vc_mlp_new = VotingClassifier([(str(i), ForwardMLPModel4(label_offset=i, path=path_new_big)) for i in range(len(np.unique(y_train)))], voting="soft")

    return make_pipeline(preprocess, vc_mlp_new)


def make_forward_mlp_model_new_label_permutation(categorical_features):
    path = "models_diff/prior_diff_real_checkpoint_output_attention_nlayer6_mlp_emsize_512_multiclass_04_17_2023_23_11_02_n_0_epoch_94.cpkt"
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    vc_mlp_new = VotingClassifier([(str(i), ForwardMLPModel3(label_offset=i, path=path)) for i in range(len(np.unique(y_train)))], voting="soft")
    return make_pipeline(preprocess, vc_mlp_new)



def make_distilled_tabpfn(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=100, device="cuda"))

def make_distilled_tabpfn_ht(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=100, temperature=10, device="cuda"))



def make_mlp_shallow(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, TorchMLP(n_epochs=100, hidden_size=128, n_layers=1, device="cuda"))

def make_distilled_tabpfn_shallow(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=100, device="cuda", hidden_size=128, n_layers=1))

def make_mlp_big(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, TorchMLP(n_epochs=100, hidden_size=1024, n_layers=4, device="cuda"))

def make_distilled_tabpfn_big(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=100, device="cuda", hidden_size=1024, n_layers=4))

def make_distilled_tabpfn_big_layernorm(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=100, device="cuda", hidden_size=1024, n_layers=4, layernorm=True))

def make_distilled_tabpfn_big_dropout(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=100, device="cuda", hidden_size=1024, n_layers=4, dropout_rate=0.2))

def make_distilled_tabpfn_big_long(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=1000, device="cuda", hidden_size=1024, n_layers=4))

def make_distilled_tabpfn_parameters_tuned(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLP(n_epochs=1000, device="cuda", hidden_size=128, n_layers=2, dropout_rate=.1, learning_rate=0.01))

def make_tabpfn_mine(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    model_string = "defaults_k_aggregate_2_batch_128_onehot_classes_multiclass_02_10_2023_23_55_16"
    tabpfn = TabPFNClassifier(device='cuda', model_string=model_string, epoch=82, N_ensemble_configurations=3)
    return make_pipeline(preprocess, tabpfn)

def make_tabpfn_mine_32(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    model_string = "defaults_k_aggregate_2_batch_128_onehot_classes_multiclass_02_10_2023_23_55_16"
    tabpfn = TabPFNClassifier(device='cuda', model_string=model_string, epoch=82, N_ensemble_configurations=32)
    return make_pipeline(preprocess, tabpfn)


def make_tabpfn_mine_32_no_onehot(categorical_features):
    model_string = "defaults_k_aggregate_2_batch_128_onehot_classes_multiclass_02_10_2023_23_55_16"
    tabpfn = TabPFNClassifier(device='cuda', model_string=model_string, epoch=82, N_ensemble_configurations=32)
    return tabpfn


def make_tabpfn_distilled_tuned_mine(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    model_string = "defaults_k_aggregate_2_batch_128_onehot_classes_multiclass_02_10_2023_23_55_16"
    clf = DistilledTabPFNMLP(n_epochs=1000, device="cuda", hidden_size=128, n_layers=2, dropout_rate=.1, learning_rate=0.01, model_string=model_string, epoch=82, )
    return make_pipeline(preprocess, clf)

def make_tabpfn_32(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, TabPFNClassifier(N_ensemble_configurations=32))


def make_distilled_tabpfn_parameters_tuned_upsample_per_batch(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    return make_pipeline(preprocess, DistilledTabPFNMLPUpsampler(n_epochs=1000, device="cuda", hidden_size=128, n_layers=2, dropout_rate=.1, learning_rate=0.01, upsample_rate=2))

def make_tabpfn_distilled_tuned_mine(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    model_string = "defaults_k_aggregate_2_batch_128_onehot_classes_multiclass_02_10_2023_23_55_16"
    clf = DistilledTabPFNMLP(n_epochs=1000, device="cuda", hidden_size=128, n_layers=2, dropout_rate=.1, learning_rate=0.01, model_string=model_string, epoch=82, )
    return make_pipeline(preprocess, clf)

def make_tabpfn_distilled_tuned_mine_quick(categorical_features):
    cont_pipe = make_pipeline(StandardScaler(), SimpleImputer())
    preprocess = make_column_transformer((OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=10), categorical_features), remainder=cont_pipe)
    model_string = "defaults_k_aggregate_2_batch_128_onehot_classes_multiclass_02_10_2023_23_55_16"
    clf = DistilledTabPFNMLP(n_epochs=100, device="cuda", hidden_size=128, n_layers=2, dropout_rate=.1, learning_rate=0.01, model_string=model_string, epoch=82, )
    return make_pipeline(preprocess, clf)