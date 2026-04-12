import React from 'react';

type BadgeVariant = 'stock' | 'display' | 'sold' | 'returned' | 'default';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  stock: 'bg-gray-100 text-gray-700',
  display: 'bg-blue-100 text-blue-700',
  sold: 'bg-green-100 text-green-700',
  returned: 'bg-red-100 text-red-700',
  default: 'bg-gray-100 text-gray-700',
};

export default function Badge({
  variant = 'default',
  children,
  className = '',
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
