"""Casos do lab 06. churn/bug: True/False = rótulo; None = não avaliado (ambíguo de propósito)."""

# (id, categoria, churn, bug, texto)
INTENT = [
    # retratação: intenção de sair existiu e foi retirada → churn False
    ("r1", "retraction", False, False, "Eu ia cancelar, mas a atualização nova resolveu meu problema. Desconsiderem o pedido de cancelamento que abri ontem."),
    ("r2", "retraction", False, False, "Semana passada pedi o cancelamento, mas conversei com meu sócio e vamos continuar. Podem reativar a conta?"),
    ("r3", "retraction", False, False, "Ignorem meu e-mail anterior sobre encerrar o contrato. Decidimos renovar por mais um ano."),
    ("r4", "retraction", False, None, "Pensei seriamente em sair no mês passado por causa das quedas, mas desde então está estável e estou satisfeito."),
    ("r5", "retraction", False, False, "Cheguei a pedir proposta do concorrente, mas desisti. Vou ficar com vocês. Só preciso atualizar o cartão."),
    ("r6", "retraction", False, False, "Retiro o que disse sobre cancelar. O suporte resolveu tudo hoje cedo."),
    # terceiro: o cancelamento/defeito é de outra empresa ou outra pessoa → False
    ("p1", "third_party", False, False, "Estamos saindo do concorrente porque o sistema deles vive caindo e a cobrança é um caos. Quero entender os planos de vocês."),
    ("p2", "third_party", False, False, "Meu colega cancelou a conta dele ano passado por cobrança errada, mas meu caso é outro: queria saber como exportar relatórios."),
    ("p3", "third_party", False, False, "Cancelei minha assinatura da ferramenta antiga para migrar tudo para vocês. Como importo meus dados?"),
    ("p4", "third_party", False, False, "Meu contador comentou que vários clientes dele abandonaram o sistema X por causa de bugs. Vocês têm integração com o sistema X?"),
    ("p5", "third_party", False, False, "A empresa do meu irmão encerrou o contrato com o fornecedor deles porque o app travava. Ele me indicou vocês. Qual o preço?"),
    ("p6", "third_party", False, False, "Li numa avaliação que um cliente de vocês cancelou por falta de suporte. Isso já foi resolvido? Estou pensando em contratar."),
    # negação simples
    ("n1", "negation", False, False, "Não quero cancelar, só quero mudar a forma de pagamento."),
    ("n2", "negation", False, False, "Não tenho intenção nenhuma de cancelar. Só queria registrar que o preço está alto."),
    ("n3", "negation", False, False, "Não é bug, o sistema funciona bem. Só quero a nota fiscal."),
    ("n4", "negation", False, True, "Não quero reembolso e não vou cancelar. Só quero que consertem a exportação de PDF, que quebrou de novo."),
    ("n5", "negation", False, False, "Nunca pensei em trocar de ferramenta. Como adiciono mais usuários?"),
    ("n6", "negation", False, False, "Nenhum erro por aqui, tudo funcionando. Só uma dúvida sobre o plano anual."),
    # controles positivos: a mitigação não pode matar o recall
    ("c1", "control", True, False, "Quero cancelar minha assinatura hoje."),
    ("c2", "control", True, None, "Se o sistema cair mais uma vez, encerramos o contrato."),
    ("c3", "control", True, False, "Eu não ia cancelar, mas depois desse aumento mudei de ideia. Encerrem a conta."),
    ("c4", "control", True, False, "Meu colega está satisfeito com vocês, mas eu não: vou migrar para o concorrente no mês que vem."),
    ("c5", "control", True, False, "Desconsiderem meu pedido de upgrade. Na verdade quero cancelar."),
    ("c6", "control", False, True, "O app trava toda vez que abro relatórios."),
    ("c7", "control", True, True, "O sistema do concorrente nunca travava. O de vocês trava todo dia. Estou voltando para eles."),
    ("c8", "control", False, True, "Não é culpa do meu navegador: o botão salvar de vocês não funciona em nenhum computador daqui."),
]

# (id, esperado, texto) — contagem de problemas distintos
COUNT = [
    ("k1", "one", "A exportação de CSV está com colunas trocadas."),
    ("k2", "two", "Fui cobrado em dobro e o app trava na tela de pagamentos."),
    ("k3", "three", "Três coisas: o login falha no Safari, a nota fiscal veio com CNPJ errado e o relatório semanal não chegou."),
    ("k4", "four_or_more", "Login falha, fatura veio errada, relatório não chega e o app do celular não abre."),
    ("k5", "one", "Tenho 3 filiais e 12 usuários, e o único problema é que o relatório mensal sai em branco."),
    ("k6", "three", "O painel está lento. Além disso a cobrança veio duplicada. Ah, e o e-mail de boas-vindas dos novos usuários não é enviado."),
]

# (id, pagou_antes_do_vencimento, texto) — ordenação de datas em texto
DATES = [
    ("d1", True, "Vencimento: 10/09/2026. Pagamento: 08/09/2026."),
    ("d2", False, "Vencimento: 10/09/2026. Pagamento: 12/09/2026."),
    ("d3", True, "Venceu em 5 de março de 2026 e paguei em 28 de fevereiro de 2026."),
    ("d4", False, "Venceu em 28 de fevereiro de 2026 e paguei em 5 de março de 2026."),
    ("d5", True, "Due 2026-01-15, paid 2025-12-30."),
    ("d6", False, "Due 2025-12-30, paid 2026-01-15."),
]
