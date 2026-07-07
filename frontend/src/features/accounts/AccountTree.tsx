"use client";

import { ChevronDown, ChevronRight, Pencil, Trash2 } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { formatMoney } from "../../lib/formatting";
import { AccountItem, AccountTreeNode, BankItem } from "../../lib/types";

type Props = {
  accounts: AccountItem[];
  banks: BankItem[];
  onEdit: (account: AccountItem) => void;
  onArchive: (account: AccountItem) => void;
};

function buildTree(accounts: AccountItem[]): AccountTreeNode[] {
  const nodes = new Map<number, AccountTreeNode>();
  accounts.forEach((account) => {
    nodes.set(account.id, {
      ...account,
      account_type: account.account_type || account.type,
      account_level: account.account_level || 1,
      direct_balance: account.current_balance,
      rollup_balance: account.current_balance,
      children: [],
    });
  });
  const roots: AccountTreeNode[] = [];
  for (const node of nodes.values()) {
    const parent = node.parent_account_id ? nodes.get(node.parent_account_id) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  const rollup = (node: AccountTreeNode): number => {
    node.children.sort((a, b) => (a.display_order || 0) - (b.display_order || 0) || a.name.localeCompare(b.name));
    node.rollup_balance = Number(node.current_balance || 0) + node.children.reduce((sum, child) => sum + rollup(child), 0);
    return node.rollup_balance;
  };
  roots.sort((a, b) => (a.display_order || 0) - (b.display_order || 0) || a.name.localeCompare(b.name));
  roots.forEach(rollup);
  return roots;
}

export function AccountTree({ accounts, banks, onEdit, onArchive }: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const bankName = (bankId: number) => banks.find((bank) => bank.id === bankId)?.name || "Unknown bank";
  const toggle = (id: number) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const render = (node: AccountTreeNode, depth = 0): React.ReactNode => {
    const hasChildren = node.children.length > 0;
    const isCollapsed = collapsed.has(node.id);
    return (
      <div key={node.id} className="account-tree-row-wrap">
        <article className="account-tree-row" style={{ "--depth": depth } as React.CSSProperties}>
          <button type="button" className="account-tree-toggle" onClick={() => toggle(node.id)} disabled={!hasChildren} aria-label={hasChildren ? "Toggle account children" : "No child accounts"}>
            {hasChildren ? (isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />) : <span />}
          </button>
          <span>
            <strong>{node.name}</strong>
            <small>{bankName(node.bank_id)} · {node.account_type || node.type} · level {node.account_level || depth + 1}</small>
          </span>
          <span className="account-tree-balances">
            <b>{formatMoney(node.current_balance, node.currency)}</b>
            {hasChildren && <small>Rollup {formatMoney(node.rollup_balance, node.currency)}</small>}
          </span>
          <div className="managed-actions">
            <button type="button" onClick={() => onEdit(node)}><Pencil size={15} />Edit</button>
            <button type="button" className="danger-action" onClick={() => onArchive(node)}><Trash2 size={15} />Archive</button>
          </div>
        </article>
        {hasChildren && !isCollapsed && <div>{node.children.map((child) => render(child, depth + 1))}</div>}
      </div>
    );
  };
  const tree = buildTree(accounts.filter((account) => account.is_active !== false));
  if (!tree.length) return <p className="muted">No accounts yet. Add your first account.</p>;
  return <div className="account-tree">{tree.map((node) => render(node))}</div>;
}

export const ACCOUNT_TYPE_OPTIONS = [
  { value: "bank", label: "Bank / institution" },
  { value: "current_account", label: "Current account" },
  { value: "savings_account", label: "Savings account" },
  { value: "cash", label: "Cash" },
  { value: "wallet", label: "Wallet" },
  { value: "card_container", label: "Card container" },
  { value: "payment_method", label: "Payment method" },
  { value: "investment", label: "Investment / broker" },
  { value: "insurance", label: "Insurance" },
  { value: "benefit", label: "Benefit" },
  { value: "other", label: "Other" },
];
