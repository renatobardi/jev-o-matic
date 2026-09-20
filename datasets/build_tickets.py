"""Fonte do dataset de tickets (sintético, escrito à mão por Claude, revisão por amostragem do Bardi).
Rodar: uv run python datasets/build_tickets.py  → datasets/tickets_v1.1.jsonl

v1.1 (2026-09-20, revisão Bardi): has_bug=True em t061 (cartão recusado só no nosso checkout),
t077 (relatórios de instantâneo p/ 40s), t081 (e-mail de reset não chega). Mantidos: t045, t075, t078.
tickets_v1.jsonl fica congelado (base do run 20260920T000223Z).

Rótulos
  dept    : billing | technical | sales | retention   (time que DEVE tratar primeiro)
  alt     : segundo dept aceitável em caso ambíguo (ou None)
  urg     : 0 pode esperar · 1 resolver esta semana · 2 precisa de ação hoje
  refund  : cliente quer dinheiro de volta (explícito OU claramente implícito)
  churn   : cliente ameaça/anuncia cancelar ou sair
  bug     : cliente relata defeito de software
  diff    : easy | ambiguous | hard
  tags    : implicit, negation, sarcasm, multi, distractor, short, typos, polite_angry, conditional, third_party
"""

import json
from collections import Counter
from pathlib import Path

B, T, S, R = "billing", "technical", "sales", "retention"

# (dept, alt, urg, refund, churn, bug, diff, tags, pt, en)
ROWS = [
    # ---------------- billing · easy
    (B, None, 1, 1, 0, 0, "easy", "", "Fui cobrado duas vezes este mês no cartão. Por favor, estornem a cobrança duplicada.", "I was charged twice this month on my card. Please refund the duplicate charge."),
    (B, None, 1, 1, 0, 0, "easy", "", "Meu plano é de R$ 99 mas veio R$ 149 na fatura. Quero a diferença de volta.", "My plan is $99 but the invoice shows $149. I want the difference back."),
    (B, None, 0, 0, 0, 0, "easy", "", "Preciso da nota fiscal de agosto com o CNPJ da empresa para a contabilidade.", "I need the August invoice with our company tax ID for accounting."),
    (B, None, 0, 0, 0, 0, "easy", "", "Meu cartão venceu. Como atualizo a forma de pagamento?", "My card expired. How do I update my payment method?"),
    (B, None, 2, 0, 0, 0, "easy", "", "Paguei o boleto há 5 dias e ainda consta em aberto. O aviso diz que a conta será suspensa amanhã.", "I paid the bank slip 5 days ago and it still shows as unpaid. The notice says my account will be suspended tomorrow."),
    (B, None, 0, 0, 0, 0, "easy", "", "Gostaria de mudar o vencimento da fatura para o dia 15.", "I would like to change my billing date to the 15th."),
    (B, None, 1, 1, 0, 0, "easy", "", "Cancelei mês passado e mesmo assim fui cobrado de novo. Quero meu dinheiro de volta.", "I cancelled last month and was still charged again. I want my money back."),
    (B, None, 0, 0, 0, 0, "easy", "", "Não recebi o recibo do pagamento de setembro. Podem reenviar?", "I did not receive the receipt for the September payment. Can you resend it?"),
    (B, None, 1, 1, 0, 0, "easy", "", "Escolhi o plano mensal e vocês cobraram o anual inteiro. Peço o estorno e a cobrança correta.", "I chose the monthly plan and you charged the full annual one. Please refund it and charge the right amount."),
    (B, None, 0, 0, 0, 0, "easy", "", "Qual a diferença entre o valor da fatura e o valor que aparece no painel? Tem imposto incluso?", "Why is the invoice amount different from the one on the dashboard? Are taxes included?"),
    (B, None, 1, 0, 0, 0, "easy", "", "Preciso trocar o cartão da cobrança antes do próximo vencimento, que é na quinta.", "I need to change the billing card before the next due date, which is Thursday."),
    (B, None, 1, 1, 0, 0, "easy", "", "Comprei créditos extras por engano ontem, não usei nenhum. Dá pra estornar?", "I bought extra credits by mistake yesterday and used none. Can you refund them?"),
    (B, None, 0, 0, 0, 0, "easy", "", "Vocês aceitam pagamento por PIX para o plano anual?", "Do you accept bank transfer for the annual plan?"),
    (B, None, 1, 0, 0, 0, "easy", "", "A fatura veio no nome da empresa antiga. Precisa ser reemitida com a razão social nova.", "The invoice was issued to our old company name. It needs to be reissued with the new legal name."),
    # ---------------- technical · easy
    (T, None, 2, 0, 0, 1, "easy", "", "O app fecha sozinho toda vez que abro a tela de relatórios. Não consigo trabalhar.", "The app crashes every time I open the reports screen. I cannot work."),
    (T, None, 1, 0, 0, 1, "easy", "", "A exportação para CSV está saindo com as colunas trocadas desde a atualização de ontem.", "The CSV export has had its columns swapped since yesterday's update."),
    (T, None, 2, 0, 0, 1, "easy", "", "Ninguém da minha equipe consegue fazer login desde as 9h. Dá erro 500.", "Nobody on my team has been able to log in since 9am. It returns error 500."),
    (T, None, 0, 0, 0, 0, "easy", "", "Como configuro o webhook para receber eventos de pagamento aprovado?", "How do I set up the webhook to receive payment-approved events?"),
    (T, None, 1, 0, 0, 1, "easy", "", "As notificações por e-mail pararam de chegar há três dias. Já olhei o spam.", "Email notifications stopped arriving three days ago. I already checked spam."),
    (T, None, 0, 0, 0, 0, "easy", "", "Tem documentação da API de relatórios? Não achei o endpoint de filtros.", "Is there documentation for the reports API? I could not find the filters endpoint."),
    (T, None, 1, 0, 0, 1, "easy", "", "O botão de salvar não faz nada no Safari. No Chrome funciona.", "The save button does nothing in Safari. It works in Chrome."),
    (T, None, 2, 0, 0, 1, "easy", "", "A integração com nosso ERP parou de sincronizar pedidos há duas horas e estamos com a expedição parada.", "The integration with our ERP stopped syncing orders two hours ago and our shipping is halted."),
    (T, None, 0, 0, 0, 0, "easy", "", "É possível aumentar o limite de requisições da API? Estamos batendo no teto às vezes.", "Is it possible to raise the API rate limit? We hit the ceiling sometimes."),
    (T, None, 1, 0, 0, 1, "easy", "", "O gráfico do dashboard mostra dados de ontem mesmo depois de atualizar a página.", "The dashboard chart shows yesterday's data even after refreshing the page."),
    (T, None, 1, 0, 0, 1, "easy", "", "Upload de arquivo acima de 10MB falha com timeout. A documentação diz que o limite é 50MB.", "Uploading files over 10MB fails with a timeout. The docs say the limit is 50MB."),
    (T, None, 0, 0, 0, 0, "easy", "", "Como faço para adicionar autenticação em dois fatores na conta?", "How do I enable two-factor authentication on my account?"),
    (T, None, 1, 0, 0, 1, "easy", "", "O app do Android não abre mais depois da última versão. Fica na tela branca.", "The Android app no longer opens after the latest version. It stays on a white screen."),
    (T, None, 2, 0, 0, 1, "easy", "", "Os dados de um cliente nosso estão aparecendo na conta de outro cliente. Isso é gravíssimo.", "One of our customers' data is showing up in another customer's account. This is extremely serious."),
    # ---------------- sales · easy
    (S, None, 0, 0, 0, 0, "easy", "", "Quanto custa o plano empresarial para 50 usuários?", "How much is the enterprise plan for 50 users?"),
    (S, None, 0, 0, 0, 0, "easy", "", "Quero fazer upgrade do básico para o pro. Muda algo nos meus dados?", "I want to upgrade from basic to pro. Does anything change with my data?"),
    (S, None, 0, 0, 0, 0, "easy", "", "Vocês têm desconto para ONGs?", "Do you offer a discount for nonprofits?"),
    (S, None, 1, 0, 0, 0, "easy", "", "Precisamos de uma proposta formal até sexta para levar ao comitê de compras.", "We need a formal quote by Friday to take to our procurement committee."),
    (S, None, 0, 0, 0, 0, "easy", "", "Dá para testar o módulo de relatórios avançados antes de contratar?", "Can we trial the advanced reports module before buying?"),
    (S, None, 0, 0, 0, 0, "easy", "", "Qual a diferença entre o plano pro e o empresarial?", "What is the difference between the pro and enterprise plans?"),
    (S, None, 0, 0, 0, 0, "easy", "", "Gostaria de agendar uma demonstração para o time de operações.", "I would like to schedule a demo for our operations team."),
    (S, None, 0, 0, 0, 0, "easy", "", "Se eu contratar o anual, consigo adicionar usuários no meio do contrato?", "If I sign the annual plan, can I add users mid-contract?"),
    (S, None, 0, 0, 0, 0, "easy", "", "Vocês têm plano para revendedores ou programa de parceiros?", "Do you have a reseller plan or a partner program?"),
    (S, None, 1, 0, 0, 0, "easy", "", "Queremos adicionar 20 licenças ainda este mês. Como procedemos?", "We want to add 20 seats this month. How do we proceed?"),
    (S, None, 0, 0, 0, 0, "easy", "", "O plano pro inclui suporte por telefone ou só no empresarial?", "Does the pro plan include phone support or only enterprise?"),
    (S, None, 0, 0, 0, 0, "easy", "", "Vocês atendem empresas fora do Brasil? Temos uma filial em Portugal.", "Do you serve companies outside Brazil? We have a branch in Portugal."),
    # ---------------- retention · easy
    (R, None, 1, 0, 1, 0, "easy", "", "Quero cancelar minha assinatura. Como faço?", "I want to cancel my subscription. How do I do it?"),
    (R, None, 1, 0, 1, 0, "easy", "", "Estamos migrando para outro fornecedor no mês que vem. Preciso encerrar o contrato.", "We are moving to another vendor next month. I need to terminate the contract."),
    (R, None, 1, 0, 1, 0, "easy", "", "O preço subiu demais. Se não tiver uma condição melhor, vou cancelar.", "The price went up too much. Unless there is a better deal, I will cancel."),
    (R, None, 0, 0, 1, 0, "easy", "", "Não uso mais o produto faz meses. Podem encerrar a conta.", "I have not used the product in months. You can close the account."),
    (R, None, 1, 0, 1, 0, "easy", "", "O concorrente me ofereceu o mesmo por metade do preço. Vocês cobrem?", "A competitor offered me the same for half the price. Can you match it?"),
    (R, None, 0, 0, 1, 0, "easy", "", "Quero pausar a assinatura por três meses em vez de cancelar. É possível?", "I want to pause the subscription for three months instead of cancelling. Is that possible?"),
    (R, None, 1, 0, 1, 0, "easy", "", "A empresa vai fechar. Preciso cancelar tudo e exportar meus dados antes.", "The company is closing down. I need to cancel everything and export my data first."),
    (R, None, 1, 0, 1, 0, "easy", "", "Quero fazer downgrade para o plano gratuito. Não vale mais o que pago.", "I want to downgrade to the free plan. It is no longer worth what I pay."),
    (R, None, 1, 0, 1, 0, "easy", "", "Meu contrato renova dia 30 e não quero renovar. Avisem o que precisam de mim.", "My contract renews on the 30th and I do not want to renew. Tell me what you need from me."),
    (R, None, 1, 0, 1, 0, "easy", "", "Sinceramente o produto não evoluiu nada em um ano. Estou avaliando sair.", "Frankly the product has not evolved at all in a year. I am considering leaving."),
    # ---------------- more easy, mixed signals that are still clear
    (B, None, 1, 1, 0, 0, "easy", "polite_angry", "Boa tarde, tudo bem? Vi que fui cobrado em duplicidade. Poderiam, por gentileza, providenciar o estorno? Obrigado!", "Good afternoon, hope you are well. I noticed I was charged twice. Could you kindly arrange a refund? Thank you!"),
    (T, None, 0, 0, 0, 1, "easy", "polite_angry", "Oi! Nada urgente, mas o ícone do menu fica desalinhado no modo escuro. Só avisando :)", "Hi! Nothing urgent, but the menu icon is misaligned in dark mode. Just letting you know :)"),
    (S, None, 0, 0, 0, 0, "easy", "short", "preço plano pro?", "pro plan price?"),
    (R, None, 1, 0, 1, 0, "easy", "short", "cancelar", "cancel"),
    (T, None, 1, 0, 0, 1, "easy", "short", "login não funciona", "login not working"),
    (B, None, 0, 0, 0, 0, "easy", "short", "segunda via boleto", "resend invoice"),
    (T, None, 1, 0, 0, 1, "easy", "typos", "o sistma ta dando erro qdo clico em salvr, ja tentei 3x e nd", "systm gives error when i clik save, tried 3x alredy nothing"),
    (B, None, 1, 1, 0, 0, "easy", "typos", "cobraram 2x meu cartao!!! qero o dinhero d volta", "u charged my card 2x!!! i wnt my mony back"),
    (S, None, 0, 0, 0, 0, "easy", "third_party", "Meu chefe pediu para eu levantar o preço de vocês para 200 usuários. Pode me mandar?", "My boss asked me to get your pricing for 200 users. Can you send it?"),
    (T, None, 2, 0, 0, 1, "easy", "", "Sistema fora do ar para todos os nossos 300 atendentes. Cada minuto é prejuízo.", "System is down for all 300 of our agents. Every minute is a loss."),
    # ---------------- ambiguous (dept discutível → alt)
    (B, T, 2, 0, 0, 1, "ambiguous", "", "Meu cartão é recusado no checkout de vocês três vezes seguidas, mas funciona em qualquer outro site. Preciso pagar hoje para não suspender.", "My card gets declined at your checkout three times in a row but works everywhere else. I need to pay today to avoid suspension."),
    (T, B, 1, 0, 0, 1, "ambiguous", "", "A tela de faturas não carrega, fica girando. Preciso baixar a nota fiscal.", "The invoices page never loads, it just spins. I need to download my invoice."),
    (R, B, 1, 1, 1, 0, "ambiguous", "multi", "Quero cancelar e receber de volta o proporcional do anual que paguei em julho.", "I want to cancel and get back the prorated amount of the annual plan I paid in July."),
    (R, T, 2, 0, 1, 1, "ambiguous", "multi", "Terceira queda do sistema este mês. Se acontecer de novo, a gente sai. Agora está fora do ar outra vez.", "Third outage this month. If it happens again, we are out. It is down again right now."),
    (S, R, 1, 0, 1, 0, "ambiguous", "", "Estou comparando vocês com dois concorrentes para renovar. O que conseguem fazer no preço?", "I am comparing you with two competitors for renewal. What can you do on price?"),
    (B, S, 0, 0, 0, 0, "ambiguous", "", "Se eu mudar do mensal para o anual agora, como fica a cobrança do mês que já paguei?", "If I switch from monthly to annual now, what happens to the month I already paid?"),
    (T, S, 0, 0, 0, 0, "ambiguous", "", "A API do plano pro suporta SSO com SAML ou precisa do empresarial?", "Does the pro plan API support SAML SSO or do I need enterprise?"),
    (B, R, 1, 1, 1, 0, "ambiguous", "conditional", "Fui cobrado por um upgrade que não pedi. Ou estornam, ou cancelo tudo.", "I was charged for an upgrade I never requested. Either you refund it or I cancel everything."),
    (T, R, 1, 0, 1, 1, "ambiguous", "", "O app está tão lento que meu time voltou a usar planilha. Não sei por quanto tempo seguimos assim.", "The app is so slow my team went back to spreadsheets. I do not know how long we can go on like this."),
    (S, B, 0, 0, 0, 0, "ambiguous", "", "Recebi um cupom de 20% por e-mail mas não achei onde aplicar na renovação.", "I got a 20% coupon by email but could not find where to apply it on renewal."),
    (B, T, 1, 1, 0, 1, "ambiguous", "multi", "O sistema travou no meio do pagamento e debitou duas vezes. Quero o estorno de uma.", "The system froze mid-payment and debited me twice. I want one of them refunded."),
    (R, S, 0, 0, 1, 0, "ambiguous", "", "Uso 10% do que o plano oferece. Tem algo menor ou é melhor eu sair?", "I use 10% of what the plan offers. Is there something smaller or should I just leave?"),
    (T, B, 1, 0, 0, 1, "ambiguous", "", "Paguei o upgrade ontem e os recursos do pro continuam bloqueados na minha conta.", "I paid for the upgrade yesterday and the pro features are still locked on my account."),
    (S, T, 0, 0, 0, 0, "ambiguous", "", "Antes de fechar o contrato preciso saber se vocês integram com SAP. Tem alguém técnico que possa confirmar?", "Before signing I need to know whether you integrate with SAP. Is there someone technical who can confirm?"),
    (B, None, 1, 0, 0, 0, "ambiguous", "", "Tem uma cobrança de R$ 37,90 no meu extrato com o nome de vocês que eu não reconheço.", "There is a $37.90 charge on my statement under your name that I do not recognize."),
    (R, None, 1, 0, 0, 0, "ambiguous", "", "Onde fica o botão de cancelar? Só quero saber onde fica, por enquanto.", "Where is the cancel button? I just want to know where it is, for now."),
    (T, None, 1, 0, 0, 1, "ambiguous", "", "Desde ontem os relatórios demoram uns 40 segundos para abrir. Antes era instantâneo. Pode ser minha internet, não sei.", "Since yesterday the reports take about 40 seconds to open. It used to be instant. Could be my connection, not sure."),
    (B, None, 2, 1, 0, 0, "ambiguous", "", "Debitaram R$ 4.800 em vez de R$ 480. Isso zerou a conta da empresa e tenho folha para pagar amanhã.", "You debited $4,800 instead of $480. That emptied the company account and I have payroll due tomorrow."),
    (S, None, 0, 0, 0, 0, "ambiguous", "", "Vi que vocês lançaram um módulo de IA. Já está incluso no que eu pago?", "I saw you launched an AI module. Is it already included in what I pay?"),
    (R, B, 1, 1, 1, 0, "ambiguous", "multi", "Cancelei em agosto, tenho o e-mail de confirmação, e continuam cobrando. Parem e devolvam os dois meses.", "I cancelled in August, I have the confirmation email, and you keep charging me. Stop and return the two months."),
    (T, None, 1, 0, 0, 1, "ambiguous", "", "Não consigo entrar. Acho que esqueci a senha, mas o e-mail de redefinição também não chega.", "I cannot get in. I think I forgot my password, but the reset email never arrives either."),
    (S, R, 1, 0, 0, 0, "ambiguous", "", "Nosso contrato vence em 30 dias. Quero renegociar valores e escopo antes de decidir qualquer coisa.", "Our contract expires in 30 days. I want to renegotiate price and scope before deciding anything."),
    (B, None, 0, 0, 0, 0, "ambiguous", "", "Vocês emitem nota com retenção de ISS? Meu financeiro está perguntando antes de aprovar o pagamento.", "Do you issue invoices with tax withholding? My finance team is asking before approving the payment."),
    (T, R, 2, 0, 1, 1, "ambiguous", "multi", "Perdemos os dados de uma semana inteira por causa do bug de sincronização. Quero falar com um gerente hoje ou encerramos.", "We lost a full week of data because of the sync bug. I want to talk to a manager today or we terminate."),
    (R, None, 0, 0, 0, 0, "ambiguous", "", "Qual é a multa se eu sair do contrato anual antes do fim? Só estou me informando.", "What is the penalty if I leave the annual contract early? I am only asking for information."),
    # ---------------- hard (negação, sarcasmo, implícito, distrator)
    (T, None, 1, 0, 0, 1, "hard", "negation", "Não quero reembolso e não vou cancelar. Só quero que consertem a exportação de PDF, que quebrou de novo.", "I do not want a refund and I am not going to cancel. I just want you to fix the PDF export, which broke again."),
    (B, None, 1, 0, 0, 0, "hard", "negation", "Não é bug, o sistema funciona bem. O problema é que a fatura veio com o valor errado e preciso que corrijam, não que devolvam.", "It is not a bug, the system works fine. The problem is the invoice has the wrong amount and I need it corrected, not refunded."),
    (R, None, 1, 0, 1, 0, "hard", "sarcasm", "Parabéns pelo aumento de 40% sem aviso. Excelente jeito de convencer a gente a procurar outra ferramenta.", "Congratulations on the 40% increase with no notice. Great way to convince us to look for another tool."),
    (T, None, 2, 0, 0, 1, "hard", "sarcasm", "Que maravilha, o sistema caiu bem na hora do fechamento do mês. De novo. Adoro.", "Wonderful, the system went down right at month-end closing. Again. Love it."),
    (B, None, 1, 1, 0, 0, "hard", "implicit", "Paguei por um ano de um módulo que vocês descontinuaram em dois meses. Como pretendem resolver isso?", "I paid for a year of a module you discontinued after two months. How do you intend to make this right?"),
    (R, None, 1, 0, 1, 0, "hard", "implicit", "Pode me mandar a exportação completa dos meus dados e o procedimento de encerramento de contrato?", "Can you send me a full export of my data and the contract termination procedure?"),
    (S, None, 0, 0, 0, 0, "hard", "distractor", "Não tenho nenhum problema, nada de bug nem cobrança errada nem cancelamento. Só quero saber o preço do plano para 10 pessoas.", "I have no problem at all, no bug, no wrong charge, no cancellation. I just want the price of the plan for 10 people."),
    (T, None, 1, 0, 0, 1, "hard", "distractor", "Meu colega cancelou a conta dele ano passado por causa de cobrança errada, mas o meu caso é outro: o filtro de datas retorna resultados fora do período.", "A colleague cancelled his account last year over a wrong charge, but my case is different: the date filter returns results outside the range."),
    (B, None, 0, 0, 0, 0, "hard", "negation", "Já recebi o estorno, obrigado. Só falta a nota fiscal de cancelamento da cobrança.", "I already received the refund, thank you. I only need the credit note for the cancelled charge."),
    (R, None, 1, 0, 0, 0, "hard", "negation", "Eu ia cancelar, mas a atualização nova resolveu meu problema. Desconsiderem o pedido de cancelamento que abri ontem.", "I was going to cancel, but the new update solved my problem. Please disregard the cancellation request I opened yesterday."),
    (T, None, 2, 0, 0, 1, "hard", "polite_angry", "Bom dia, equipe. Com todo respeito, faz 6 horas que nossa operação está parada por causa do erro no login e ninguém respondeu. Agradeço a atenção.", "Good morning, team. With all due respect, our operation has been down for 6 hours because of the login error and nobody has replied. Thank you for your attention."),
    (B, None, 1, 1, 0, 0, "hard", "third_party", "Minha mãe, que é idosa, assinou sem querer pelo celular e foi cobrada. Ela não usa. Precisamos reaver esse valor.", "My elderly mother subscribed by accident on her phone and was charged. She does not use it. We need to get that amount back."),
    (S, None, 0, 0, 0, 0, "hard", "distractor", "Estamos saindo do concorrente porque o sistema deles vive caindo e a cobrança é um caos. Quero entender os planos de vocês.", "We are leaving a competitor because their system keeps crashing and their billing is chaos. I want to understand your plans."),
    (R, None, 2, 0, 1, 0, "hard", "conditional", "Se até as 18h de hoje não tiver retorno de um gerente sobre a renovação, considere o contrato encerrado.", "If I do not hear back from a manager about the renewal by 6pm today, consider the contract terminated."),
    (T, None, 0, 0, 0, 0, "hard", "negation", "Não é defeito, é dúvida: o relatório considera fuso de Brasília ou UTC? Os números não batem com os meus, mas pode ser isso.", "Not a defect, just a question: does the report use local time or UTC? The numbers do not match mine, but that might be why."),
    (B, R, 1, 1, 1, 0, "hard", "sarcasm", "Ótimo, mais uma cobrança indevida. Devolvam e aproveitem para encerrar minha conta, já que é para isso que vocês trabalham.", "Great, yet another wrongful charge. Refund it and go ahead and close my account, since that seems to be what you are working toward."),
]


def main() -> None:
    out = Path(__file__).with_name("tickets_v1.1.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for i, (dept, alt, urg, refund, churn, bug, diff, tags, pt, en) in enumerate(ROWS, 1):
            f.write(json.dumps({
                "id": f"t{i:03d}", "difficulty": diff, "tags": tags.split(",") if tags else [],
                "text": {"pt": pt, "en": en},
                "labels": {"department": dept, "alt_department": alt, "urgency": urg,
                           "refund_wanted": bool(refund), "churn_threat": bool(churn), "has_bug": bool(bug)},
            }, ensure_ascii=False) + "\n")
    print(f"{len(ROWS)} tickets → {out.name}")
    for name, idx in [("dept", 0), ("urg", 2), ("diff", 6)]:
        print(f"  {name}: {dict(Counter(r[idx] for r in ROWS))}")
    for name, idx in [("refund", 3), ("churn", 4), ("bug", 5)]:
        print(f"  {name}=1: {sum(r[idx] for r in ROWS)}")


if __name__ == "__main__":
    main()
