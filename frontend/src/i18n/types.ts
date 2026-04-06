export type Locale = "pt" | "en";

export interface TranslationDictionary {
  /* ── Common ── */
  "common.loading": string;
  "common.cancel": string;
  "common.save": string;
  "common.close": string;
  "common.delete": string;
  "common.or": string;
  "common.back": string;
  "common.year_singular": string;
  "common.year_plural": string;
  "common.month_singular": string;
  "common.month_plural": string;
  "common.day_singular": string;
  "common.day_plural": string;
  "common.hour_singular": string;
  "common.hour_plural": string;
  "common.minute_singular": string;
  "common.minute_plural": string;
  "common.companies": string;
  "common.of_analysis": string;
  "common.na": string;

  /* ── Header ── */
  "header.tagline": string;

  /* ── Footer ── */
  "footer.tool_by": string;
  "footer.past_results": string;
  "footer.looking_for_partners": string;
  "footer.cumulative_return": string;

  /* ── Auth ── */
  "auth.login": string;
  "auth.signup": string;
  "auth.email": string;
  "auth.password": string;
  "auth.min_8_chars": string;
  "auth.confirm_password": string;
  "auth.allow_contact": string;
  "auth.passwords_dont_match": string;
  "auth.wrong_credentials": string;
  "auth.signup_error": string;
  "auth.connection_error": string;
  "auth.logging_in": string;
  "auth.creating": string;
  "auth.create_account": string;
  "auth.forgot_password": string;
  "auth.continue_with_google": string;
  "auth.my_account": string;
  "auth.restricted_access": string;
  "auth.must_be_logged_in": string;
  "auth.do_login": string;
  "auth.account_created": string;
  "auth.account_created_text": string;
  "auth.go_to_homepage": string;
  "auth.member_since": string;
  "auth.change_password": string;
  "auth.logout": string;
  "auth.back_to_homepage": string;
  "auth.change_password_title": string;
  "auth.current_password": string;
  "auth.new_password": string;
  "auth.confirm_new_password": string;
  "auth.change_password_error": string;
  "auth.password_changed": string;
  "auth.saving": string;
  "auth.change_password_button": string;

  /* ── Forgot / Reset Password ── */
  "forgot.title": string;
  "forgot.description": string;
  "forgot.email_sent": string;
  "forgot.email_sent_text": string;
  "forgot.back_to_login": string;
  "forgot.send_error": string;
  "forgot.sending": string;
  "forgot.send_link": string;
  "reset.title": string;
  "reset.invalid_link": string;
  "reset.invalid_link_text": string;
  "reset.request_new_link": string;
  "reset.success_title": string;
  "reset.success_text": string;
  "reset.new_password": string;
  "reset.confirm_new_password": string;
  "reset.error": string;
  "reset.saving": string;
  "reset.submit": string;

  /* ── Verify Email ── */
  "verify.verifying": string;
  "verify.success_title": string;
  "verify.success_text": string;
  "verify.invalid_link": string;
  "verify.invalid_token": string;
  "verify.error": string;
  "verify.expired_text": string;

  /* ── Feedback ── */
  "feedback.trigger": string;
  "feedback.title": string;
  "feedback.subtitle": string;
  "feedback.email_label": string;
  "feedback.message_label": string;
  "feedback.message_placeholder": string;
  "feedback.math_question": string;
  "feedback.wrong_answer": string;
  "feedback.send_error": string;
  "feedback.sending": string;
  "feedback.send": string;
  "feedback.thanks": string;
  "feedback.thanks_text": string;

  /* ── Search ── */
  "search.aria_label": string;
  "search.placeholder": string;

  /* ── Share ── */
  "share.label": string;
  "share.copied": string;
  "share.copy_link": string;
  "share.text_with_ticker": string;
  "share.text_without_ticker": string;

  /* ── Favorites ── */
  "favorites.title": string;
  "favorites.add": string;
  "favorites.remove": string;
  "favorites.add_prominent": string;
  "favorites.add_card_title": string;
  "favorites.search_placeholder": string;

  /* ── Popular ── */
  "popular.title": string;

  /* ── Quota ── */
  "quota.limit_reached": string;
  "quota.create_account": string;
  "quota.to_continue": string;

  /* ── Tabs ── */
  "tabs.metrics": string;
  "tabs.fundamentals": string;
  "tabs.compare": string;
  "tabs.charts": string;

  /* ── Sector Peers ── */
  "sector.same_sector": string;

  /* ── Compare ── */
  "compare.debt_group": string;
  "compare.profitability_group": string;
  "compare.valuation_group": string;
  "compare.company": string;
  "compare.analyzing_last": string;
  "compare.auth_reorder": string;
  "compare.rename": string;
  "compare.duplicate": string;
  "compare.rename_list": string;
  "compare.new_name": string;
  "compare.delete_list": string;
  "compare.delete_confirm": string;
  "compare.duplicate_list": string;
  "compare.save_list": string;
  "compare.list_name": string;
  "compare.data_unavailable": string;
  "compare.add_company": string;

  /* ── Fundamentals ── */
  "fundamentals.nominal": string;
  "fundamentals.ipca": string;
  "fundamentals.cpi": string;
  "fundamentals.balance": string;
  "fundamentals.income": string;
  "fundamentals.cash_flow": string;
  "fundamentals.returns": string;
  "fundamentals.year": string;
  "fundamentals.no_data": string;

  /* ── Fundamentals Column Labels ── */
  "fundamentals.col.debt": string;
  "fundamentals.col.liabilities": string;
  "fundamentals.col.equity": string;
  "fundamentals.col.debt_equity": string;
  "fundamentals.col.liab_equity": string;
  "fundamentals.col.current_ratio": string;
  "fundamentals.col.revenue": string;
  "fundamentals.col.net_income": string;
  "fundamentals.col.fcf": string;
  "fundamentals.col.operating_cf": string;
  "fundamentals.col.market_cap": string;
  "fundamentals.col.dividends": string;
  "fundamentals.col.pe10": string;
  "fundamentals.col.pe5": string;
  "fundamentals.col.pfcf10": string;
  "fundamentals.col.pfcf5": string;

  /* ── Charts ── */
  "charts.no_data": string;
  "charts.adjusted_price": string;
  "charts.what_is_adjusted": string;
  "charts.adjusted_explanation": string;
  "charts.historical": string;

  /* ── Chart Month Names ── */
  "charts.month.jan": string;
  "charts.month.feb": string;
  "charts.month.mar": string;
  "charts.month.apr": string;
  "charts.month.may": string;
  "charts.month.jun": string;
  "charts.month.jul": string;
  "charts.month.aug": string;
  "charts.month.sep": string;
  "charts.month.oct": string;
  "charts.month.nov": string;
  "charts.month.dec": string;

  /* ── Company Metrics Card ── */
  "metrics.more_info": string;
  "metrics.debt_section": string;
  "metrics.financial_note": string;
  "metrics.price_vs_results": string;
  "metrics.slider_caption": string;
  "metrics.slider_drag_hint": string;
  "metrics.annual_warning": string;
  "metrics.current_price": string;
  "metrics.market_cap": string;
  "metrics.years_of_data": string;
  "metrics.gross_debt_equity": string;
  "metrics.debt_ex_lease_equity": string;
  "metrics.liab_equity": string;
  "metrics.gross_debt_earnings": string;
  "metrics.gross_debt_fcf": string;
  "metrics.average": string;
  "metrics.cagr_earnings": string;
  "metrics.cagr_fcf": string;
  "metrics.real": string;
  "metrics.lynch": string;

  /* ── Metrics Modal Explainers ── */
  "modal.balance_date": string;
  "modal.reference": string;
  "modal.components": string;
  "modal.calculation": string;
  "modal.gross_debt": string;
  "modal.leases": string;
  "modal.total_liabilities": string;
  "modal.equity": string;
  "modal.result": string;
  "modal.note": string;
  "modal.how_calculated": string;

  "modal.debt_equity_explain": string;
  "modal.debt_equity_compare": string;
  "modal.debt_ex_lease_explain": string;
  "modal.liab_equity_explain": string;
  "modal.liab_equity_broader": string;
  "modal.debt_earnings_explain": string;
  "modal.debt_earnings_note": string;
  "modal.debt_fcf_explain": string;

  "modal.pl10_explain": string;
  "modal.pl10_high_low": string;
  "modal.pl10_how_title": string;
  "modal.pl10_step1": string;
  "modal.pl10_step2": string;
  "modal.pl10_step3": string;
  "modal.pl10_col_year": string;
  "modal.pl10_col_net_income": string;
  "modal.pl10_col_ipca_factor": string;
  "modal.pl10_col_cpi_factor": string;
  "modal.pl10_col_adjusted": string;
  "modal.pl10_sum": string;
  "modal.pl10_avg_label": string;
  "modal.pl10_market_cap": string;
  "modal.pl10_divided_by": string;

  "modal.pfcl10_explain": string;
  "modal.pfcl10_compare": string;
  "modal.pfcl10_step1": string;
  "modal.pfcl10_col_fcf": string;
  "modal.pfcl10_col_adjusted": string;
  "modal.pfcl10_step2": string;
  "modal.pfcl10_sum": string;
  "modal.pfcl10_avg_label": string;
  "modal.pfcl10_divided_by": string;

  "modal.peg_explain": string;
  "modal.peg_below_one": string;
  "modal.pfclg_complement": string;
  "modal.cagr_explain": string;
  "modal.cagr_endpoint": string;
  "modal.cagr_regression": string;
  "modal.cagr_default": string;
  "modal.cagr_result": string;
  "modal.cagr_real_earnings": string;
  "modal.cagr_real_fcf": string;
  "modal.peg_excluded_note": string;

  "modal.title.debt_equity": string;
  "modal.title.debt_ex_lease": string;
  "modal.title.liab_equity": string;
  "modal.title.debt_earnings": string;
  "modal.title.debt_fcf": string;
  "modal.title.peg": string;
  "modal.title.cagr_earnings": string;
  "modal.title.pfclg": string;
  "modal.title.cagr_fcf": string;

  "modal.quarterly_net_income": string;
  "modal.quarterly_operating": string;
  "modal.quarterly_investing": string;

  /* ── PE10 Explainer ── */
  "explainer.hide": string;
  "explainer.what_is_pe10": string;
  "explainer.pe10_text_1": string;
  "explainer.pe10_text_2": string;
  "explainer.pe10_text_3": string;
  "explainer.what_is_pfcf10": string;
  "explainer.pfcf10_text_1": string;
  "explainer.pfcf10_text_2": string;
  "explainer.pfcf10_fcf_vs_earnings": string;
  "explainer.pfcf10_text_3": string;
  "explainer.pfcf10_text_4": string;

  /* ── Company Analysis ── */
  "analysis.long_term": string;
  "analysis.previous_versions": string;
  "analysis.attribution": string;

  /* ── Homepage Cards ── */
  "homepage.price": string;
  "homepage.market_cap": string;
  "homepage.equity": string;
  "homepage.liabilities": string;
  "homepage.gross_debt": string;
  "homepage.current_ratio": string;
  "homepage.auth_save_layout": string;
  "homepage.debt_fcf": string;
  "homepage.pe10": string;
  "homepage.pfcf10": string;
  "homepage.cagr_earnings_short": string;
  "homepage.cagr_fcf_short": string;
  "homepage.price_to_book": string;

  /* ── Saved Lists ── */
  "lists.your_lists": string;
  "lists.see_all": string;
  "lists.and_more": string;
  "lists.term": string;
  "lists.view_full": string;
  "lists.more": string;
  "lists.page_title": string;
  "lists.page_hint": string;
  "lists.no_lists": string;
  "lists.must_login": string;

  /* ── Shared List ── */
  "shared.not_found": string;
  "shared.expired_text": string;
  "shared.title": string;
  "shared.shared_list": string;
  "shared.view_list": string;

  /* ── Subsector Names ── */
  "subsector.banks": string;
  "subsector.insurance": string;
  "subsector.construction": string;
  "subsector.malls": string;
  "subsector.rental": string;
  "subsector.agribusiness": string;
  "subsector.market_infra": string;
  "subsector.holdings": string;

  /* ── Language Toggle ── */
  "language.toggle_label": string;
}

export type TranslationKey = keyof TranslationDictionary;
