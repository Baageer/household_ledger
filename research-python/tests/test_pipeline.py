import pandas as pd
from unittest.mock import patch
from pathlib import Path

from ledger.pipeline import analyze_dataframe, analyze_directory, analyze_file


def sample_frame():
    return pd.DataFrame(
        {
            "交易时间": ["2026-08-01 09:00", "2026-08-01 12:00", "2026-08-01 12:00", "2026-08-02 10:00"],
            "交易对方": ["工资", "美团外卖", "美团外卖", "滴滴出行"],
            "金额": ["+10000", "-56", "-56", "32"],
            "收/支": ["收入", "支出", "支出", "支出"],
            "支付方式": ["招商银行", "微信", "微信", "支付宝"],
            "交易单号": ["salary-1", "order-1", "order-1", "order-2"],
        }
    )


def test_pipeline_deduplicates_classifies_and_summarises():
    result = analyze_dataframe(sample_frame(), source="wechat")
    assert result["total_count"] == 4
    assert result["duplicate_count"] == 1
    assert result["posted_count"] == 3
    assert result["totals"] == {"income": 10000.0, "expense": 88.0, "balance": 9912.0}
    assert list(result["category_summary"]["category"]) == ["餐饮", "交通"]
    assert result["posted"].iloc[1]["category"] == "餐饮"


def test_unknown_merchant_is_low_confidence_other():
    frame = pd.DataFrame({"日期": ["2026-08-01"], "商户": ["陌生商户"], "金额": [-10]})
    result = analyze_dataframe(frame)
    assert result["posted"].iloc[0]["category"] == "其他"
    assert result["posted"].iloc[0]["confidence"] < 0.5


def test_transfer_is_not_counted_as_household_income_or_expense():
    frame = pd.DataFrame(
        {
            "日期": ["2026-08-01", "2026-08-01"],
            "商户": ["招商银行", "支付宝"],
            "金额": [-5000, 5000],
            "收支": ["转账", "转账"],
        }
    )
    result = analyze_dataframe(frame)
    assert result["totals"] == {"income": 0.0, "expense": 0.0, "balance": 0.0}
    assert set(result["posted"]["category"]) == {"转账"}


def test_directory_merges_files_and_deduplicates_across_files(tmp_path):
    first = tmp_path / "alipay.xlsx"
    second = tmp_path / "alipay-duplicate.xlsx"
    first.touch()
    second.touch()
    frames = {
        str(first): sample_frame().iloc[:2],
        str(second): sample_frame().iloc[1:3],
    }
    def fake_read_excel(path, **kwargs):
        frame = frames[str(path)]
        if kwargs.get("header") is None:
            return pd.concat([pd.DataFrame([frame.columns]), frame.reset_index(drop=True)], ignore_index=True)
        return frame

    with patch("ledger.pipeline.pd.read_excel", side_effect=fake_read_excel):
        result = analyze_directory(tmp_path)
    assert result["file_count"] == 2
    assert result["total_count"] == 4
    assert result["duplicate_count"] == 2
    assert result["posted_count"] == 2


def test_neutral_transaction_is_not_counted():
    frame = pd.DataFrame({"日期": ["2026-08-01"], "商户": ["账户转存"], "金额": [100], "收支": ["不计收支"]})
    result = analyze_dataframe(frame)
    assert result["totals"] == {"income": 0.0, "expense": 0.0, "balance": 0.0}
    assert result["posted"].iloc[0]["category"] == "不计收支"


def test_alipay_export_csv_with_metadata_rows_is_supported():
    path = Path(__file__).parent / "test_JUL" / "支付宝交易明细(20260727-20260827).csv"
    result = analyze_file(path)
    assert result["total_count"] == 77
    assert result["posted_count"] == 77
