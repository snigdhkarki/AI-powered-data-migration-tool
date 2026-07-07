import streamlit as st
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder
from st_aggrid.shared import GridUpdateMode
import google.generativeai as genai

# Import the AI validator from the separate module
from ai_validator import validate_row_with_gemini

# -------------------------------
# Helper: type-safe value conversion
# -------------------------------
def convert_edited_value(value, original_series):
    """Try to convert edited string value to the original column's dtype"""
    if pd.isna(value) or value == "":
        return None

    if pd.api.types.is_integer_dtype(original_series):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            st.error(f"Invalid integer value: '{value}'. Please enter a whole number.")
            return None
    elif pd.api.types.is_float_dtype(original_series):
        try:
            return float(value)
        except (ValueError, TypeError):
            st.error(f"Invalid float value: '{value}'. Please enter a number.")
            return None
    elif pd.api.types.is_bool_dtype(original_series):
        if value.lower() in ['true', 'yes', '1']:
            return True
        elif value.lower() in ['false', 'no', '0']:
            return False
        else:
            st.error(f"Invalid boolean value: '{value}'. Use True/False or Yes/No.")
            return None
    else:
        return str(value)


# -------------------------------
# Helper: load source + optional dest checkpoint
# -------------------------------
def load_checkpoint(source_file, dest_file):
    """Load source and optional destination files."""
    try:
        source_df = pd.read_csv(source_file)
        if source_df.empty:
            st.error("Source CSV is empty.")
            return None, None
    except Exception as e:
        st.error(f"Error reading source CSV: {e}")
        return None, None

    if dest_file is not None:
        try:
            target_df = pd.read_csv(dest_file)
            if list(target_df.columns) != list(source_df.columns):
                st.error("Destination CSV columns do not match source CSV columns.")
                return None, None
        except Exception as e:
            st.error(f"Error reading destination CSV: {e}")
            return None, None
    else:
        target_df = pd.DataFrame(columns=source_df.columns)

    return source_df, target_df


# -------------------------------
# Main app
# -------------------------------
def main():
    st.set_page_config(page_title="CSV Row Migrator with Validation", layout="wide")
    st.title("📋 CSV Row Migration Tool with Column Validation")
    st.markdown("Upload a source CSV and optionally a destination checkpoint to resume.")

    # ── Initialize session state keys ─────────────────────────────────────
    if "column_descriptions" not in st.session_state:
        st.session_state.column_descriptions = {}
    if "row_validation_cache" not in st.session_state:
        st.session_state.row_validation_cache = {}
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "descriptions_set" not in st.session_state:
        st.session_state.descriptions_set = False

    col1, col2 = st.columns(2)
    with col1:
        source_file = st.file_uploader("📂 Source CSV (required)", type=["csv"], key="source_upload")
    with col2:
        dest_file = st.file_uploader("📂 Destination CSV (optional, for resuming)", type=["csv"], key="dest_upload")

    # ── Destination grid version counter ────────────────────────────────
    if "dest_grid_version" not in st.session_state:
        st.session_state.dest_grid_version = 0

    # ── Load / reset session state when files change ────────────────────
    if source_file is not None:
        current_source_name = source_file.name
        current_dest_name = dest_file.name if dest_file else None

        if (
            "source_df" not in st.session_state
            or st.session_state.get("source_filename") != current_source_name
            or st.session_state.get("dest_filename") != current_dest_name
        ):
            source_df, target_df = load_checkpoint(source_file, dest_file)
            if source_df is not None:
                st.session_state.source_df = source_df
                st.session_state.target_df = target_df
                st.session_state.curr_idx = 0
                st.session_state.modify_mode = False
                st.session_state.source_filename = current_source_name
                st.session_state.dest_filename = current_dest_name
                st.session_state.history = []
                st.session_state.dest_grid_version = 0
                st.session_state.descriptions_set = False
                st.session_state.column_descriptions = {}
                st.session_state.row_validation_cache = {}
                st.success(
                    f"Loaded {len(source_df)} source rows. "
                    f"Destination has {len(target_df)} rows."
                )
                st.rerun()
    else:
        st.info("👈 Please upload a source CSV file to begin.")
        return

    # ── Pull working copies from session state ─────────────────────────
    source_df = st.session_state.source_df
    target_df = st.session_state.target_df
    curr_idx = st.session_state.curr_idx
    total_rows = len(source_df)

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📊 Progress")
        st.metric("Rows Processed", curr_idx)
        st.metric("Rows Accepted", len(target_df))
        st.metric("Rows Remaining", total_rows - curr_idx)
        if total_rows > 0:
            st.progress(curr_idx / total_rows)

        st.divider()
        st.header("🔑 Gemini API Key")
        api_key = st.text_input(
            "Enter your Gemini API key",
            type="password",
            value=st.session_state.api_key,
            help="Get one from https://makersuite.google.com/app/apikey"
        )
        if api_key != st.session_state.api_key:
            st.session_state.api_key = api_key
            # Clear cache when key changes
            st.session_state.row_validation_cache = {}
            genai.configure(api_key=api_key)
        elif api_key:
            genai.configure(api_key=api_key)

        st.divider()
        st.header("↩️ Undo")
        if st.button(
            "↩️ Undo Last Action",
            use_container_width=True,
            disabled=len(st.session_state.history) == 0,
        ):
            last_action = st.session_state.history.pop()
            if last_action["type"] == "accept":
                st.session_state.target_df = st.session_state.target_df.iloc[:-1]
                st.session_state.dest_grid_version += 1
            # Clear validation cache for the undone row if needed
            if last_action.get("row_idx") is not None:
                st.session_state.row_validation_cache.pop(last_action["row_idx"], None)
            st.session_state.curr_idx -= 1
            st.rerun()

        st.divider()
        st.header("💾 Checkpoint")
        if total_rows - curr_idx > 0:
            remaining_df = source_df.iloc[curr_idx:]
            if not remaining_df.empty:
                st.download_button(
                    label="📥 Download Remaining Source",
                    data=remaining_df.to_csv(index=False),
                    file_name="source_remaining.csv",
                    mime="text/csv",
                )
        if not target_df.empty:
            st.download_button(
                label="📥 Download Destination",
                data=target_df.to_csv(index=False),
                file_name="destination.csv",
                mime="text/csv",
            )
        st.caption("Save both files to resume later.")

        st.divider()
        st.header("🔄 Actions")
        if st.button("🆕 Start New Migration", use_container_width=True):
            for key in [
                "source_df", "target_df", "curr_idx", "modify_mode",
                "source_filename", "dest_filename", "history", "dest_grid_version",
                "column_descriptions", "row_validation_cache", "descriptions_set"
            ]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        if st.button("🗑️ Clear Destination", use_container_width=True):
            st.session_state.target_df = pd.DataFrame(columns=source_df.columns)
            st.session_state.dest_grid_version += 1
            st.rerun()

        if st.button("✏️ Edit Column Descriptions", use_container_width=True):
            st.session_state.descriptions_set = False
            st.rerun()

    # ── Column Descriptions configuration ──────────────────────────────
    if not st.session_state.descriptions_set:
        st.subheader("📝 Define Column Descriptions")
        st.markdown("For each column, provide a description that the value should satisfy. This will be used to validate each cell.")
        with st.form(key="desc_form"):
            descriptions = {}
            cols = st.columns(3)
            for i, col in enumerate(source_df.columns):
                with cols[i % 3]:
                    default_desc = st.session_state.column_descriptions.get(col, "")
                    desc = st.text_input(f"**{col}**", value=default_desc, placeholder="e.g. must be a valid email")
                    descriptions[col] = desc
            submitted = st.form_submit_button("💾 Save Descriptions")
            if submitted:
                st.session_state.column_descriptions = descriptions
                st.session_state.descriptions_set = True
                st.session_state.row_validation_cache = {}  # clear old cache
                st.rerun()
        st.stop()  # Stop execution until descriptions are saved

    # ── Main content area ────────────────────────────────────────────────
    col_main, col_dest = st.columns([2, 1])

    # ── Destination table (right column) ────────────────────────────────
    with col_dest:
        st.subheader("✅ Destination Table")
        st.caption("Click any cell to edit it, then press 💾 Save Changes.")

        if not target_df.empty:
            gb = GridOptionsBuilder.from_dataframe(target_df)
            gb.configure_default_column(
                editable=True,
                resizable=True,
                filterable=True,
                sortable=True,
                minWidth=100,
                width=150,
                wrapText=False,
                autoHeight=False,
            )
            gb.configure_grid_options(rowHeight=35)
            gb.configure_grid_options(domLayout="normal")
            dest_grid_options = gb.build()

            grid_key = f"dest_grid_{len(target_df)}_{st.session_state.dest_grid_version}"

            dest_grid_response = AgGrid(
                target_df.copy(),
                gridOptions=dest_grid_options,
                height=350,
                width="100%",
                update_mode=GridUpdateMode.MODEL_CHANGED,
                allow_unsafe_jscode=True,
                theme="streamlit",
                key=grid_key,
                reload_data=False,
            )

            if st.button("💾 Save Changes", use_container_width=True, key="save_dest_btn"):
                if dest_grid_response["data"] is not None:
                    edited_df = pd.DataFrame(dest_grid_response["data"])
                    if not edited_df.empty:
                        edited_df = edited_df.reindex(columns=source_df.columns)
                    else:
                        edited_df = pd.DataFrame(columns=source_df.columns)
                    st.session_state.target_df = edited_df
                    st.session_state.dest_grid_version += 1
                    st.success("✅ Destination changes saved!")
                    st.rerun()
        else:
            st.info("No rows accepted yet.")

    # ── Row-by-row processing (left column) ─────────────────────────────
    with col_main:
        if curr_idx >= total_rows:
            st.success("🎉 All rows have been processed!")
            st.balloons()
            st.info(
                f"Migration complete. Accepted {len(target_df)} out of {total_rows} rows."
            )
        else:
            current_row = source_df.iloc[curr_idx]
            st.subheader(f"📄 Row {curr_idx + 1} of {total_rows}")

            # ── Validate row using Gemini (if not cached) ──────────────
            if st.session_state.api_key:
                validation_result = validate_row_with_gemini(
                    curr_idx, current_row,
                    st.session_state.column_descriptions,
                    st.session_state.api_key
                )
            else:
                validation_result = None
                st.warning("Gemini API key not provided. Validation skipped.")

            # ── Display row with colors ────────────────────────────────
            if not st.session_state.modify_mode:
                row_df = pd.DataFrame([current_row])

                if validation_result is not None:
                    # Apply styling using Styler.apply (axis=1) to get column names
                    def style_row(row):
                        styles = []
                        for col in row.index:
                            if col in validation_result:
                                if validation_result[col]:
                                    styles.append('background-color: #d4edda; color: #000000;')
                                else:
                                    styles.append('background-color: #f8d7da; color: #000000;')
                            else:
                                styles.append('')
                        return pd.Series(styles, index=row.index) 
                    styled = row_df.style.apply(style_row, axis=1)
                    st.dataframe(styled, use_container_width=True)
                else:
                    st.dataframe(row_df, use_container_width=True)

                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button("✅ Accept", type="primary", use_container_width=True):
                        st.session_state.target_df = pd.concat(
                            [target_df, pd.DataFrame([current_row])],
                            ignore_index=True,
                        )
                        st.session_state.history.append({"type": "accept", "row_idx": curr_idx})
                        st.session_state.curr_idx += 1
                        st.rerun()

                with col_b:
                    if st.button("❌ Reject", use_container_width=True):
                        st.session_state.history.append({"type": "reject", "row_idx": curr_idx})
                        st.session_state.curr_idx += 1
                        st.session_state.row_validation_cache.pop(curr_idx, None)
                        st.rerun()

                with col_c:
                    if st.button("✏️ Modify", use_container_width=True):
                        st.session_state.modify_mode = True
                        st.rerun()
            else:
                # ── Modify mode ────────────────────────────────────────
                st.markdown("**✏️ Edit row values below**")
                st.caption("Modify any field, then click 'Save Modified Row'")

                modified_values = {}
                with st.form(key="modify_form"):
                    for col in source_df.columns:
                        original_val = current_row[col]
                        display_val = "" if pd.isna(original_val) else str(original_val)
                        modified_values[col] = st.text_input(
                            f"**{col}**",
                            value=display_val,
                            key=f"mod_{col}_{curr_idx}",
                        )

                    st.markdown("---")
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        submitted = st.form_submit_button(
                            "💾 Save Modified Row", type="primary", use_container_width=True
                        )
                    with col_cancel:
                        cancelled = st.form_submit_button(
                            "❌ Cancel", use_container_width=True
                        )

                    if submitted:
                        converted_row = {}
                        conversion_error = False

                        for col in source_df.columns:
                            edited_val = modified_values[col]
                            converted = convert_edited_value(edited_val, source_df[col])

                            if (
                                converted is None
                                and edited_val != ""
                                and not pd.isna(edited_val)
                            ):
                                conversion_error = True
                                st.error(
                                    f"❌ Invalid value for column '{col}': '{edited_val}'"
                                )
                                break
                            converted_row[col] = converted

                        if not conversion_error:
                            st.session_state.target_df = pd.concat(
                                [target_df, pd.DataFrame([converted_row])],
                                ignore_index=True,
                            )
                            st.session_state.history.append({"type": "accept", "row_idx": curr_idx})
                            st.session_state.row_validation_cache.pop(curr_idx, None)
                            st.session_state.modify_mode = False
                            st.session_state.curr_idx += 1
                            st.rerun()

                    if cancelled:
                        st.session_state.modify_mode = False
                        st.rerun()


if __name__ == "__main__":
    main()