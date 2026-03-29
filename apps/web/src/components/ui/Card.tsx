import React from 'react';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export default function Card({ title, children, className = '' }: CardProps) {
  return (
    <div
      className={`bg-white rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow ${className}`}
    >
      {title && (
        <h3 className="text-lg font-semibold text-black mb-4">{title}</h3>
      )}
      {children}
    </div>
  );
}
