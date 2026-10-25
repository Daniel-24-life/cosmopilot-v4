"""New public fixtures. No competition data, real customers or brand assets."""

def case(sid, title, service, risk, quote, fact, missing, draft, late=None):
    messages = [{"seq": 1, "speaker": "消费者", "text": quote},
                {"seq": 2, "speaker": "客服", "text": "收到，我先核对记录与可用资料。"}]
    evidence = [{"id": "E1", "kind": "buyer_report", "available_seq": 1, "text": quote},
                {"id": "E2", "kind": "verified", "available_seq": 2, "text": fact},
                {"id": "E3", "kind": "inference", "available_seq": 2, "text": "建议按当前服务类型准备人工回复。"}]
    if late:
        messages.append({"seq": 3, "speaker": "客服", "text": late})
        evidence.append({"id": "E4", "kind": "verified", "available_seq": 3, "text": late})
    return {"id": sid, "title": title, "service": service, "risk": risk,
            "messages": messages, "evidence": evidence, "missing": missing,
            "draft": draft, "source_ticket": "开放", "synthetic": True}


CASES = [
    case("DEMO-001", "日常通勤，怎样缩小选品范围", "选品咨询", "普通",
         "想找日常通勤用的彩妆，还没有确定具体色号。",
         "合成目录有两款演示商品；色号适配、库存和个体使用效果未知。",
         ["使用偏好", "色号适配", "实际库存"],
         "可以先按使用场景与妆效偏好缩小范围，再确认色号。目录仅作演示参考，不代表库存或适用承诺。"),
    case("DEMO-002", "使用后不适，需要优先转人工", "不良反应", "高风险",
         "用了以后感到不舒服，想知道应该找谁处理。",
         "当前资料只有消费者自述，没有医疗结论或独立核验。",
         ["人工核验记录", "专业处理意见"],
         "已记录您反馈的不适，建议先暂停使用，并转由人工服务核对处理。这里无法判断原因或作医疗诊断。"),
    case("DEMO-003", "退货进度与退款状态要分开", "售后退货", "普通",
         "退货已经寄出了，退款是不是也到账了？",
         "演示退货记录为运输中；没有退款到账凭证。",
         ["仓库签收", "退款审核", "到账凭证"],
         "当前演示记录显示退货运输中；暂时没有退款到账凭证。可以先核对签收和审核进度，到账情况仍待确认。"),
    case("DEMO-004", "缺件补发，还缺收货核验", "补发换货", "普通",
         "收到的包裹少了一件，能帮忙核实吗？",
         "合成订单包含两件商品；尚未取得缺件核验结果。",
         ["缺件核验", "收货信息确认", "补发授权"],
         "可以先核对订单明细与缺件情况，再由人工确认补发条件。当前尚未创建补发单，也没有发货结果。"),
    case("DEMO-005", "工单结束，款项仍需核对", "订单款项", "高风险",
         "页面说问题处理完了，钱什么时候能到？",
         "演示工单显示处理完成；款项状态没有可核验的到账记录。",
         ["款项凭证", "支付渠道状态", "到账时间"],
         "工单处理完成与款项到账是不同状态。目前没有可核验的到账记录，需继续核对支付渠道和凭证，不承诺到账时间。"),
    case("DEMO-006", "按消息时点查看，不读取未来证据", "售后退货", "普通",
         "请帮我看看退货现在到了哪一步。",
         "第二条消息时点仅知道包裹已寄出，尚无签收记录。",
         ["后续处理记录"],
         "可以按当前可见记录核对退货进度，后续状态需以对应时点的证据为准。",
         late="第三条消息时点新增合成签收记录；仍无退款到账凭证。"),
]
