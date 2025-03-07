import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt
import pandas as pd
import xarray as xr
from scipy.optimize import curve_fit, minimize_scalar


def generate_fourier_modes(
    periods: npt.NDArray[np.float_], n_order: int
) -> pd.DataFrame:
    """Generate Fourier modes.

    Parameters
    ----------
    periods : array-like of float
        Input array denoting the period range.
    n_order : int
        Maximum order of Fourier modes.

    Returns
    -------
    pd.DataFrame
        Fourier modes (sin and cos with different frequencies) as columns in a dataframe.

    References
    ----------
    See :ref:`examples:Air_passengers-Prophet_with_Bayesian_workflow` in PyMC examples collection.
    """
    if n_order < 1:
        raise ValueError("n_order must be greater than or equal to 1")
    return pd.DataFrame(
        {
            f"{func}_order_{order}": getattr(np, func)(2 * np.pi * periods * order)
            for order in range(1, n_order + 1)
            for func in ("sin", "cos")
        }
    )


def michaelis_menten(
    x: Union[float, np.ndarray, npt.NDArray[np.float64]],
    alpha: Union[float, np.ndarray, npt.NDArray[np.float64]],
    lam: Union[float, np.ndarray, npt.NDArray[np.float64]],
) -> Union[float, Any]:
    """
    Evaluate the Michaelis-Menten function for given values of x, alpha, and lambda.

    The Michaelis-Menten function is a type of mathematical saturation function commonly used in
    enzyme kinetics, but it's also applicable in marketing mix models to describe
    how different channels contribute to a certain outcome (e.g., sales or conversions)
    as the spending on that channel increases and the contribution saturates.

    Mathematically, it is described as:
    α * x / (λ + x)

    Parameters
    ----------
    x : float
        The spent on a channel.
    alpha (Limit/Vmax) : float
        The maximum contribution a channel can make.
    lam (k) : float
        The elbow on the function in `x` (Point where the curve change their direction).

    Returns
    -------
    float
        The value of the Michaelis-Menten function given the parameters.
    """

    return alpha * x / (lam + x)


def extense_sigmoid(
    x: Union[float, np.ndarray, npt.NDArray[np.float64]],
    alpha: Union[float, np.ndarray, npt.NDArray[np.float64]],
    lam: Union[float, np.ndarray, npt.NDArray[np.float64]],
) -> Union[float, Any]:
    """
    Parameters
    ----------
    - alpha
        α (alpha): Represent the Asymptotic Maximum or Ceiling Value.
    - lam
        λ (lambda): affects how quickly the function approaches its upper and lower asymptotes. A higher value of
        lam makes the curve steeper, while a lower value makes it more gradual.
    """

    if alpha <= 0 or lam <= 0:
        raise ValueError("alpha and lam must be greater than 0")

    return (alpha - alpha * np.exp(-lam * x)) / (1 + np.exp(-lam * x))


def estimate_menten_parameters(
    channel: Union[str, Any],
    original_dataframe: Union[pd.DataFrame, Any],
    contributions: Union[xr.DataArray, Any],
    **kwargs,
) -> List[float]:
    """
    Estimate the parameters for the Michaelis-Menten function using curve fitting.

    This function extracts the relevant data for the specified channel from both
    the original_dataframe and contributions DataArray resulting from the model.
    It then utilizes scipy's curve_fit method to find the optimal parameters for
    an Menten function, aiming to minimize the least squares difference between
    the observed and predicted data.

    Parameters
    ----------
    channel : str
        The name of the marketing channel for which parameters are to be estimated.
    original_dataframe : Union[pd.DataFrame, Any]
        The original DataFrame containing the channel data.
    contributions : xr.DataArray
        An xarray DataArray containing the contributions data, indexed by channel.

    Returns
    -------
    List[float]
        The estimated parameters of the extended sigmoid function.
    """
    maxfev = kwargs.get("maxfev", 5000)
    lam_initial_estimate = kwargs.get("lam_initial_estimate", 0.001)

    x = kwargs.get("x", original_dataframe[channel].to_numpy())
    y = kwargs.get("y", contributions.sel(channel=channel).to_numpy())

    alpha_initial_estimate = kwargs.get("alpha_initial_estimate", max(y))

    # Initial guess for L and k
    initial_guess = [alpha_initial_estimate, lam_initial_estimate]
    # Curve fitting
    popt, pcov = curve_fit(michaelis_menten, x, y, p0=initial_guess, maxfev=maxfev)

    # Save the parameters
    return popt


def estimate_sigmoid_parameters(
    channel: Union[str, Any],
    original_dataframe: Union[pd.DataFrame, Any],
    contributions: Union[xr.DataArray, Any],
    **kwargs,
) -> List[float]:
    """
    Estimate the parameters for the sigmoid function using curve fitting.

    This function extracts the relevant data for the specified channel from both
    the original_dataframe and contributions DataArray resulting from the model.
    It then utilizes scipy's curve_fit method to find the optimal parameters for
    an sigmoid function, aiming to minimize the least squares difference between
    the observed and predicted data.

    Parameters
    ----------
    channel : str
        The name of the marketing channel for which parameters are to be estimated.
    original_dataframe : Union[pd.DataFrame, Any]
        The original DataFrame containing the channel data.
    contributions : xr.DataArray
        An xarray DataArray containing the contributions data, indexed by channel.

    Returns
    -------
    List[float]
        The estimated parameters of the extended sigmoid function.
    """
    maxfev = kwargs.get("maxfev", 5000)
    lam_initial_estimate = kwargs.get("lam_initial_estimate", 0.00001)

    x = kwargs.get("x", original_dataframe[channel].to_numpy())
    y = kwargs.get("y", contributions.sel(channel=channel).to_numpy())

    alpha_initial_estimate = kwargs.get("alpha_initial_estimate", 3 * max(y))

    parameter_bounds_modified = ([0, 0], [alpha_initial_estimate, np.inf])
    popt, _ = curve_fit(
        extense_sigmoid,
        x,
        y,
        p0=[alpha_initial_estimate, lam_initial_estimate],
        bounds=parameter_bounds_modified,
        maxfev=maxfev,
    )

    return popt


def compute_sigmoid_second_derivative(
    x: Union[float, np.ndarray, npt.NDArray[np.float64]],
    alpha: Union[float, np.ndarray, npt.NDArray[np.float64]],
    lam: Union[float, np.ndarray, npt.NDArray[np.float64]],
) -> Union[float, Any]:
    """
    Compute the second derivative of the extended sigmoid function.

    The second derivative of a function gives us information about the curvature of the function.
    In the context of the sigmoid function, it helps us identify the inflection point, which is
    the point where the function changes from being concave up to concave down, or vice versa.

    Parameters
    ----------
    x : float
        The input value for which the second derivative is to be computed.
    alpha : float
        The asymptotic maximum or ceiling value of the sigmoid function.
    lam : float
        The parameter that affects how quickly the function approaches its upper and lower asymptotes.

    Returns
    -------
    float
        The second derivative of the sigmoid function at the input value.
    """

    return (
        -alpha
        * lam**2
        * np.exp(-lam * x)
        * (1 - np.exp(-lam * x) - 2 * lam * x * np.exp(-lam * x))
        / (1 + np.exp(-lam * x)) ** 3
    )


def find_sigmoid_inflection_point(
    alpha: Union[float, np.ndarray, npt.NDArray[np.float64]],
    lam: Union[float, np.ndarray, npt.NDArray[np.float64]],
) -> Tuple[Any, float]:
    """
    Find the inflection point of the extended sigmoid function.

    The inflection point of a function is the point where the function changes its curvature,
    i.e., it changes from being concave up to concave down, or vice versa. For the sigmoid
    function, this is the point where the function has its maximum rate of growth.

    Parameters
    ----------
    alpha : float
        The asymptotic maximum or ceiling value of the sigmoid function.
    lam : float
        The parameter that affects how quickly the function approaches its upper and lower asymptotes.

    Returns
    -------
    tuple
        The x and y coordinates of the inflection point.
    """

    # Minimize the negative of the absolute value of the second derivative
    result = minimize_scalar(
        lambda x: -abs(compute_sigmoid_second_derivative(x, alpha, lam))
    )

    # Evaluate the original function at the inflection point
    x_inflection = result.x
    y_inflection = extense_sigmoid(x_inflection, alpha, lam)

    return x_inflection, y_inflection


def standardize_scenarios_dict_keys(d: Dict, keywords: List[str]):
    """
    Standardize the keys in a dictionary based on a list of keywords.

    This function iterates over the keys in the dictionary and the keywords. If a keyword is found in a key (case-insensitive),
    the key is replaced with the keyword.

    Parameters
    ----------
    d : dict
        The dictionary whose keys are to be standardized.
    keywords : list
        The list of keywords to standardize the keys to.

    Returns
    -------
    None
        The function modifies the given dictionary in-place and doesn't return any object.
    """
    for keyword in keywords:
        for key in list(d.keys()):
            if re.search(keyword, key, re.IGNORECASE):
                d[keyword] = d.pop(key)
                break


def apply_sklearn_transformer_across_dim(
    data: xr.DataArray,
    func: Callable[[np.ndarray], np.ndarray],
    dim_name: str,
    combined: bool = False,
) -> xr.DataArray:
    """Helper function in order to use scikit-learn functions with the xarray target.

    Parameters
    ----------
    data :
    func : scikit-learn method to apply to the data
    dim_name : Name of the dimension to apply the function to
    combined : Flag to indicate if the data coords have been combined or not

    Returns
    -------
    xr.DataArray
    """
    # These are lost during the ufunc
    attrs = data.attrs

    if combined:
        data = xr.apply_ufunc(
            func,
            data,
        )
    else:
        data = xr.apply_ufunc(
            func,
            data.expand_dims(dim={"_": 1}, axis=1),
            input_core_dims=[[dim_name, "_"]],
            output_core_dims=[[dim_name, "_"]],
            vectorize=True,
        ).squeeze(dim="_")

    data.attrs = attrs

    return data


def create_new_spend_data(
    spend: np.ndarray,
    adstock_max_lag: int,
    one_time: bool,
    spend_leading_up: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Create new spend data for the channel forward pass.

    Spends must be the same length as the number of channels.

    .. plot::
        :context: close-figs

        import numpy as np
        import matplotlib.pyplot as plt
        import arviz as az

        from pymc_marketing.mmm.utils import create_new_spend_data
        az.style.use("arviz-white")

        spend = np.array([1, 2])
        adstock_max_lag = 3
        one_time = True
        spend_leading_up = np.array([4, 3])
        channel_spend = create_new_spend_data(spend, adstock_max_lag, one_time, spend_leading_up)

        time_since_spend = np.arange(-adstock_max_lag, adstock_max_lag + 1)

        ax = plt.subplot()
        ax.plot(
            time_since_spend,
            channel_spend,
            "o",
            label=["Channel 1", "Channel 2"]
        )
        ax.legend()
        ax.set(
            xticks=time_since_spend,
            yticks=np.arange(0, channel_spend.max() + 1),
            xlabel="Time since spend",
            ylabel="Spend",
            title="One time spend with spends leading up",
        )
        plt.show()


    Parameters
    ---------
    spend : np.ndarray
        The spend data for the channels.
    adstock_max_lag : int
        The maximum lag for the adstock transformation.
    one_time: bool, optional
        If the spend is one-time, by default True.
    spend_leading_up : np.ndarray, optional
        The spend leading up to the first observation, by default None or 0.

    Returns
    -------
    np.ndarray
        The new spend data for the channel forward pass.
    """
    n_channels = len(spend)

    if spend_leading_up is None:
        spend_leading_up = np.zeros_like(spend)

    if len(spend_leading_up) != n_channels:
        raise ValueError("spend_leading_up must be the same length as the spend")

    spend_leading_up = np.tile(spend_leading_up, adstock_max_lag).reshape(
        adstock_max_lag, -1
    )

    spend = (
        np.vstack([spend, np.zeros((adstock_max_lag, n_channels))])
        if one_time
        else np.ones((adstock_max_lag + 1, n_channels)) * spend
    )

    return np.vstack(
        [
            spend_leading_up,
            spend,
        ]
    )
