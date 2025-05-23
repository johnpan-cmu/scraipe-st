import streamlit as st
from component_repo import ComponentRepo, ComponentMetadata, IComponentProvider, ComponentStatus
from streamlit_scroll_navigation import scroll_navbar
from utils import label2anchor
import pandas as pd
from scraipe_st.default_config import get_default_links, register_default_components
from scraipe import Workflow

from utils import get_random_wikipedia_links, get_tme_links


# Monkey patch to fix import issue. Hopefully nothing breaks
from pydantic_settings import BaseSettings
import pydantic
setattr(pydantic, "BaseSettings", BaseSettings)
import streamlit_pydantic as sp

class App:
    nav_pairs = [
        ("Links", "Edit Links"),
        ("Scraper", "Configure Scraper"),
        ("Analyzer", "Configure Analyzer"),
        ("Workflow", "Run Workflow"),]
    nav_labels = [pair[0] for pair in nav_pairs]
    nav_anchors = [label2anchor(pair[1]) for pair in nav_pairs]
    version:str

    def __init__(self, title: str ="Scraipe", version: str = "demo v0.1.0"):
        self.title = title
        self.version = version
        
        self.component_repo = ComponentRepo()
        register_default_components(self.component_repo)
        
    def get_workflow(self, scraper=None, analyzer=None) -> Workflow:
        """
        Get the workflow object from the session state.
        
        Returns:
            Workflow: The workflow object.
        """
        if "workflow" not in st.session_state:
            st.session_state["workflow"] = Workflow(scraper, analyzer)
        workflow = st.session_state["workflow"]
        if scraper is not None:
            workflow.scraper = scraper
        if analyzer is not None:
            workflow.analyzer = analyzer
        return workflow

    def main(self):
        st.set_page_config(
            page_title=self.title,
            page_icon="🧰",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        #===Sidebar and Title===
        with st.sidebar:
            st.markdown(f"<h1 style='text-align: center; font-size: 3em;'>{self.title}</h1>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align: center;'>{self.version}</h3>", unsafe_allow_html=True)
            st.divider()
            scroll_navbar(self.nav_anchors, anchor_labels=self.nav_labels)
            
        #===Links===
        st.subheader("Edit Links")

        links_upload_key = "links_upload"
        uploaded_file = st.file_uploader(
            "Choose a csv, txt, or Excel file", type=["csv","xlsx","xls","txt"],
            accept_multiple_files=False,
            key=links_upload_key,
        )
        
        if uploaded_file is not None:
            df:pd.DataFrame = None
            try:
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(uploaded_file)
                elif uploaded_file.name.endswith(".txt"):
                    df = pd.read_csv(uploaded_file, sep="\t")
                else:
                    st.error("Unsupported file type. Please upload a csv, txt, or Excel file.")    
            except Exception as e:
                st.error("Unable to read the file. Please check the file format.")
            
            if df: 
                # Validate the dataframe has a 'links' column case insensitive
                if "link" not in df.columns:
                    st.error("The uploaded file must contain URL links in the 'link' column")
                else:
                    st.session_state["initial_links_df"] = df["link"].dropna().reset_index(drop=True)
        
      
        # Set default links if no file is uploaded
        if st.session_state.get("initial_links_df") is None:
            st.session_state["initial_links_df"] = pd.DataFrame(
                data={
                    'link': get_default_links()
                }
            )
        
        with st.expander("Edit", expanded=True):
            # Use a fragment to limit rerun scope
            @st.fragment()
            def links_fragment():
                column_config = {
                    "link": st.column_config.LinkColumn("link"),
                }
                edited_links = st.data_editor(
                    st.session_state["initial_links_df"], num_rows="dynamic",
                    use_container_width=True,hide_index=True,
                    column_config=column_config,
                )
                st.session_state["links_df"] = edited_links

                
                def update_links(links,add=True):
                    # append links to the dataframe. If dataframe has extra columns, just set to null
                    new_links_df = pd.DataFrame(
                        data={
                            'link': links
                        }
                    )
                    # Check if the dataframe has extra columns that aren't 'link'
                    links_df = st.session_state["links_df"]
                    if len(links_df.columns) > 1:
                        for col in links_df.columns:
                            if col != "link":
                                new_links_df[col] = None
                    
                    # Ensure column type is str
                    new_links_df["link"] = new_links_df["link"].astype(str)
    
                    if add:
                        final_df = pd.concat( [links_df, new_links_df], ignore_index=True)
                    else:
                        final_df = new_links_df
                    # When programatically changing the dataframe going into the data_editor,
                    # update both the initial and edited dataframes and rerun                        
                    st.session_state["links_df"] = final_df
                    st.session_state["initial_links_df"] = final_df
                    
                    st.rerun(scope="fragment")
                
                col_sizes = [.05,.16,.16,.12]
                col_sizes += [1 - sum(col_sizes)]
                cols = st.columns(col_sizes,vertical_alignment="center", gap="small")
                with cols[0]:
                    st.write(f"{len(edited_links)} links")

                with cols[1]:
                    if (st.button(
                            "Add Wikipedia Links", key="generate_wiki_links", 
                            help="Generate 10 random links from Wikipedia",
                            use_container_width=True
                        )):
                        links = get_random_wikipedia_links(10)
                        update_links(links)
                with cols[2]:
                    if (st.button(
                            "Add Telegram Links", key="generate_tme_links",
                            help="Generate 10 random links from Telegram",
                            use_container_width=True
                        )):
                        links = get_tme_links(10)
                        update_links(links)
                with cols[3]:
                    if (st.button(
                            "Clear Links", key="clear_links",
                            help="Clear all links",
                            use_container_width=True
                        )):
                        update_links([],add=False)
                    
            links_fragment()
                
            
        st.divider()
        
        #===Scrapers===
        ## Display the selected scraper's metadata
        def configure_component_loop(comp:str, provider_options:list):
            st.subheader(f"Configure {comp}")
        
            # Select a scraper from the component repository
            option_indices = list(range(len(provider_options)))
            
            selected_index = st.selectbox(
                f"Select {comp}", options=option_indices,
                format_func=lambda x: provider_options[x][1].name, key=f"{comp}_selectbox")
            
            if selected_index is not None:
                selected_option = provider_options[selected_index]
                metadata:ComponentMetadata = selected_option[1]
                comp_key = f"{comp}_{metadata.name}"
                

                provider:IComponentProvider = selected_option[0]
                    
                description_cont = st.container(key=f"{comp}_description")
                # Configure the selected scisraper
                schema = provider.get_config_schema()
                config_key = f"config_{comp_key}"
                config = st.session_state.get(config_key, None)
                

                if schema:
                    from pydantic import BaseModel
                    
                    # Remove border from pydantic form
                    css = r'''
                        <style>
                            [data-testid="stForm"] {border: 0px}
                        </style>
                    '''
                    st.markdown(css, unsafe_allow_html=True)
                    
                    # Get the configured component if available
                    component,status = st.session_state.get(comp_key, (None,None))

                                        
                    # Create the expander to contain form
                    with st.expander("Details",expanded=True):
                        config:BaseModel = sp.pydantic_form(
                            f"{comp_key}_form", config or provider.get_default_config() or schema,
                            submit_label="Configure")
                        if config is not None:
                            try:
                                # Unique submission was made, create the component
                                st.session_state[comp_key] = provider.get_component_and_status(config)
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                st.error(f"Error creating {comp}: {e}")
                                st.session_state[comp_key] = None
                            else:
                                st.session_state[config_key] = config
                            component_is_new = True


                else:
                    # No config needed, just get the component as needed
                    if st.session_state.get(comp_key) is None:
                        st.session_state[comp_key] = provider.get_component_and_status(None)
                
                # Render late update for additional configuration
                component,_ = st.session_state.get(comp_key, (None,None))
                provider.late_update(component)


                # Display the component status in the description_cont container
                description_str = f"**{metadata.name}**: {metadata.description}"
                status = provider.get_component_status(component)
                if status == ComponentStatus.READY:
                    # Add green checkmark if the component is good config
                    description_str = "✔️" + description_str
                    st.session_state[comp_key] = (component, status)
                else:
                    description_str = "⚠️" + description_str
                description_cont.markdown(description_str)
                
                               
                return comp_key
        scraper_key = configure_component_loop("Scraper", self.component_repo.get_scrapers())
        st.divider()
        
        #===Analyzers===
        analyzer_key = configure_component_loop("Analyzer", self.component_repo.get_analyzers())
        st.divider()
        
        
        #===Workflow===
        st.subheader("Run Workflow")
        @st.fragment()
        def run_scrape_section():
            scraper,status = st.session_state.get(scraper_key,(None,None))
            workflow = self.get_workflow(scraper=scraper)
            
            can_run = status is not None and status == ComponentStatus.READY

            if st.button("Scrape", key="run_scrape", disabled=not can_run):
                links_df = st.session_state.get("links_df")
                links = links_df["link"].tolist()
                bar = st.progress(0.0, text="Scraping...")
                acc = 0
                workflow.clear_scrapes()
                for result in workflow.scrape_generator(links, overwrite=True):
                    bar.progress(acc/len(links), text=f"Scraping {len(links)} links...")
                    acc += 1
                bar.empty()
                df = workflow.get_scrapes()
                if "df" in df.columns:
                    df = df.drop(columns="metadata")
                st.session_state["scrapes_df"] = df 
                
            if not can_run:
                st.warning("Configure a good scraper to scrape links.")    
            
            scrapes_df = st.session_state.get("scrapes_df", None)
                
            if scrapes_df is not None and len(scrapes_df) > 0:
                column_config = {
                    "link": st.column_config.LinkColumn("Link", width="small"),
                    "content": st.column_config.TextColumn("Content", width="large"),
                    "scrape_success": st.column_config.CheckboxColumn("Success",width="small"),
                    "scrape_error": st.column_config.TextColumn("Error", width="small"),
                }
                st.dataframe(scrapes_df, use_container_width=True,
                    hide_index=True,
                    column_config=column_config,
                    key="scrape_dataframe",
                )
                
        with st.container(key="scrape_section",border=True):
            run_scrape_section()
        
        st.divider()
        
        @st.fragment()
        def run_analyze_section():
            analyzer,status = st.session_state.get(analyzer_key,(None,None))
            workflow = self.get_workflow(analyzer=analyzer)
            
            can_run = status is not None and status == ComponentStatus.READY
            
            if st.button("Analyze", key="run_analyze", disabled=not can_run):
                workflow.clear_analyses()
                bar = st.progress(0.0, text="Analyzing...")
                scrapes_df = workflow.get_scrapes()
                scrapes_length = len(scrapes_df) if scrapes_df is not None else 0
                acc = 0
                for result in workflow.analyze_generator(overwrite=True):
                    bar.progress(acc/scrapes_length, text=f"Analyzing {scrapes_length} content items....")
                    acc += 1
                bar.empty()
                st.session_state["analysis_df"] = workflow.get_analyses()
                
            if not can_run:
                st.warning("Configure a good analyzer to analyze content.")
                
            analysis_df = st.session_state.get("analysis_df", None)
            if analysis_df is not None and len(analysis_df) > 0:
                # Check for analysis_success column
                if "analysis_success" in analysis_df.columns:
                    column_config = {
                        "output": st.column_config.JsonColumn("Output", width="large"),
                        "link": st.column_config.LinkColumn("Link", width="medium"),
                        "analysis_success": st.column_config.CheckboxColumn("Success",width="small"),
                        "analysis_error": st.column_config.TextColumn("Error", width="small"),
                    }
                    st.dataframe(analysis_df, use_container_width=True,
                        hide_index=True,
                        column_config=column_config,
                        key="analyze_dataframe"
                    )
                    
                    # Fixes weird ghost element in UI bug
                    st.empty()
        with st.container(key="analyze_section",border=True):
            run_analyze_section()
            
def serve():
    """
    Serve the Streamlit app.
    
    Returns:
        None
    """
    app = App()
    app.main()
if __name__ == "__main__":
    serve()