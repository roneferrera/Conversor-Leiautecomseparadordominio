        st.markdown("---")
        st.markdown("""### Tipos X/D/C/V
| Tipo | Regra |
|------|-------|
| X | 1 debito, 1 credito |
| D | 1 debito, N creditos |
| C | N debitos, 1 credito |
| V | N debitos, N creditos |""")
        st.markdown("---")
        st.markdown("""### Versoes
**V3.1** - Tipo X em uma linha, tipo C credito primeiro
- X: DEB+CRED na mesma linha 6100
- C: credito primeiro, debitos depois
- D/V: debitos primeiro, creditos depois

**V3.0** - Arquitetura correta (1 linha por partida)

**V2.1** - Fix parse I200/I250""")

    with st.expander("Instrucoes de Uso", expanded=False):
        st.markdown("""
        <div class="instrucoes-box">
        <h4>Regras de geracao (V3.1)</h4>
        <ul>
            <li><b>Tipo X</b>: uma unica linha 6100 com debito E credito preenchidos.</li>
            <li><b>Tipo C</b>: credito na primeira linha 6100, debitos nas linhas seguintes.</li>
            <li><b>Tipos D e V</b>: debitos primeiro, creditos depois, uma linha 6100 por partida.</li>
        </ul>

        <h4>Exemplo tipo X</h4>
        <pre>|6000|X||||
|6100|07/01/2022|686|10001|4287,68||Historico|||||||</pre>

        <h4>Exemplo tipo C (2 debitos, 1 credito)</h4>
        <pre>|6000|C||||
|6100|07/01/2022||10001|4287,68||Historico|||||||
|6100|07/01/2022|686||4223,36||Historico|||||||
|6100|07/01/2022|178||64,32||Historico|||||||</pre>

        <h4>Exemplo tipo D (1 debito, 2 creditos)</h4>
        <pre>|6000|D||||
|6100|07/01/2022|686||4287,68||Historico|||||||
|6100|07/01/2022||10001|4223,36||Historico|||||||
|6100|07/01/2022||178|64,32||Historico|||||||</pre>

        <h4>Passo a passo</h4>
        <ol>
            <li>Selecione o arquivo SPED ECD.</li>
            <li>Clique em Converter.</li>
            <li>Verifique o log e baixe o arquivo.</li>
            <li>Importe no Dominio: Utilitarios, Importacao, Lancamentos em Lote.</li>
        </ol>

        <h4>Observacoes</h4>
        <ul>
            <li>Partidas com mesma conta e mesmo lado (D ou C) sao somadas.</li>
            <li>Arquivo gravado em latin-1.</li>
            <li>Lancamentos sem debito e credito simultaneos sao ignorados.</li>
        </ul>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    for k, v in [
        ("log", [f"Pronto. Versao: {VERSAO}"]),
        ("txt_gerado", None),
        ("nome_arquivo", "lancamentos.txt"),
        ("metricas", {}),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    arquivo = st.file_uploader("Arquivo SPED ECD", type=["txt"])

    st.markdown("")
    b1, b2 = st.columns(2)
    with b1:
        converter = st.button(
            "Converter",
            disabled=(arquivo is None),
            use_container_width=True,
            type="primary",
        )
    with b2:
        limpar = st.button("Limpar", use_container_width=True)

    if limpar:
        st.session_state.log          = ["Limpo."]
        st.session_state.txt_gerado   = None
        st.session_state.nome_arquivo = "lancamentos.txt"
        st.session_state.metricas     = {}
        st.rerun()

    if converter and arquivo:
        st.session_state.log        = ["Iniciando V3.1..."]
        st.session_state.txt_gerado = None
        st.session_state.metricas   = {}

        status_text  = st.empty()
        progress_bar = st.progress(0)

        linhas, ecd = converter_sped_ecd(
            arquivo.read(),
            st.session_state.log,
            progress_bar,
            status_text,
        )

        if linhas and ecd:
            progress_bar.progress(100)
            status_text.text("Concluido!")
            txt = "\n".join(linhas) + "\n"
            st.session_state.txt_gerado = txt.encode("latin-1", errors="replace")
            cnpj = re.sub(r"\D", "", ecd.cnpj)
            st.session_state.nome_arquivo = f"ECD_{cnpj}_dominio_V3.1.txt"
            st.session_state.metricas = {
                "CNPJ"        : ecd.cnpj,
                "Lanc. (6000)": sum(1 for l in linhas if l.startswith("|6000|")),
                "Linhas 6100" : sum(1 for l in linhas if l.startswith("|6100|")),
                "Total linhas": len(linhas),
            }
        else:
            progress_bar.progress(100)
            status_text.text("Falha - veja o log.")
        st.rerun()

    if st.session_state.metricas:
        st.markdown("#### Resumo")
        cols = st.columns(4)
        for i, (k, v) in enumerate(st.session_state.metricas.items()):
            cols[i].metric(k, v)

    if st.session_state.txt_gerado:
        st.success("Arquivo gerado com sucesso!")
        st.download_button(
            "Baixar arquivo convertido",
            data=st.session_state.txt_gerado,
            file_name=st.session_state.nome_arquivo,
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    st.markdown("**Log de processamento**")
    log_txt  = "\n".join(st.session_state.log)
    tem_erro = any(str(l).startswith("ERRO") for l in st.session_state.log)
    cor      = "#D32F2F" if tem_erro else "#388E3C"
    st.markdown(f"""
        <div style="background:#FCFCFC;border:1px solid {cor};border-radius:6px;
                    padding:14px;font-family:Consolas,monospace;font-size:13px;
                    white-space:pre-wrap;max-height:500px;overflow-y:auto;color:#1F1F1F;">
{log_txt}
        </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
