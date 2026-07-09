def _render_resultados_saldo_inicial(exibir_log: bool):
    metricas = st.session_state.metricas or {}
    st.markdown("---")
    st.markdown("## 📊 Resultado — Saldo Inicial (SPED ECD → Domínio)")

    if metricas:
        cols = st.columns(min(len(metricas), 5))
        items = list(metricas.items())
        for i, (k, v) in enumerate(items[:5]):
            cols[i].metric(k, v)
        if len(items) > 5:
            cols2 = st.columns(len(items) - 5)
            for i, (k, v) in enumerate(items[5:]):
                cols2[i].metric(k, v)

    bal = metricas.get("Balanceado", "")
    if "SIM" in bal:
        st.markdown(
            "<div class='card-ok'><span style='font-size:22px;'>✅</span> "
            "<b style='color:#00C896;font-size:18px;'>"
            "Lançamento de saldo inicial balanceado.</b></div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div class='card-err'><span style='font-size:22px;'>⚠️</span> "
            "<b style='color:#FF4444;font-size:18px;'>"
            "Lançamento DESBALANCEADO — verifique o relatório de erros.</b></div>",
            unsafe_allow_html=True
        )

    st.markdown("#### ⬇ Downloads")
    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        if st.session_state.resultado_bytes:
            st.success("✅ Arquivo gerado!")
            st.download_button(
                "⬇ Baixar saldo inicial (.txt)",
                data=st.session_state.resultado_bytes,
                file_name=st.session_state.resultado_nome,
                mime="text/plain",
                use_container_width=True,
                type="primary",
            )
    with dl2:
        if st.session_state.erros_bytes:
            st.error("❌ Há erros — baixe o relatório.")
            st.download_button(
                "⬇ Baixar relatório de erros",
                data=st.session_state.erros_bytes,
                file_name=st.session_state.erros_nome,
                mime="text/plain",
                use_container_width=True,
            )
    with dl3:
        if st.session_state.log_linhas:
            log_txt = "\n".join(str(l) for l in st.session_state.log_linhas)
            st.download_button(
                "⬇ Baixar log",
                data=log_txt.encode("utf-8-sig"),
                file_name="log_saldo_inicial.txt",
                mime="text/plain",
                use_container_width=True,
            )

    if exibir_log and st.session_state.log_linhas:
        st.markdown("#### 🖥 Log de Processamento")
        log_txt  = "\n".join(str(l) for l in st.session_state.log_linhas)
        tem_erro = any("ERRO" in str(l).upper() or "NÃO" in str(l).upper()
                       for l in st.session_state.log_linhas)
        st.markdown(
            f"<div class='bloco-log' style='border-color:"
            f"{'#FF4444' if tem_erro else '#1A3050'};'>{log_txt}</div>",
            unsafe_allow_html=True
        )
