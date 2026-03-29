'use client';

import React, { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Card from '@/components/ui/Card';

const categories = ['Robes', 'Hauts', 'Bas', 'Accessoires', 'Chaussures', 'Manteaux', 'Autre'];

export default function NewProductPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showLabel, setShowLabel] = useState(false);

  const [form, setForm] = useState({
    name: '',
    category: '',
    size: '',
    color: '',
    brand: '',
    purchasePrice: '',
    sellingPrice: '',
  });

  const handleChange = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleFileSelect = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setPhotoPreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      handleFileSelect(file);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Call API to create product
    router.push('/inventory');
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-500 hover:text-black min-h-[44px] transition-colors mb-4"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Retour
          </button>
          <h1 className="text-2xl font-bold text-black">Nouveau produit</h1>
        </div>

        <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Photo */}
          <div className="lg:col-span-1">
            <Card title="Photo">
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  dragOver ? 'border-teal bg-teal-50' : 'border-gray-300 hover:border-pink'
                }`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
              >
                {photoPreview ? (
                  <img // eslint-disable-line @next/next/no-img-element
                    src={photoPreview}
                    alt="Preview"
                    className="max-h-64 mx-auto rounded-lg object-contain"
                  />
                ) : (
                  <div className="space-y-3">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </svg>
                    <p className="text-gray-500 text-sm">
                      Glissez une photo ici ou cliquez pour parcourir
                    </p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
              </div>
            </Card>
          </div>

          {/* Right: Form fields */}
          <div className="lg:col-span-2 space-y-6">
            <Card title="Informations produit">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="sm:col-span-2">
                  <Input
                    label="Nom"
                    value={form.name}
                    onChange={(e) => handleChange('name', e.target.value)}
                    placeholder="Ex: Robe fleurie vintage"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">
                    Categorie
                  </label>
                  <select
                    value={form.category}
                    onChange={(e) => handleChange('category', e.target.value)}
                    className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal focus:border-teal"
                    required
                  >
                    <option value="">Choisir une categorie</option>
                    {categories.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                <Input
                  label="Taille"
                  value={form.size}
                  onChange={(e) => handleChange('size', e.target.value)}
                  placeholder="Ex: M, 38, 42..."
                />

                <Input
                  label="Couleur"
                  value={form.color}
                  onChange={(e) => handleChange('color', e.target.value)}
                  placeholder="Ex: Rose, Bleu..."
                />

                <Input
                  label="Marque"
                  value={form.brand}
                  onChange={(e) => handleChange('brand', e.target.value)}
                  placeholder="Ex: Zara, Mango..."
                />
              </div>
            </Card>

            <Card title="Tarification">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <Input
                  label="Prix d'achat"
                  type="number"
                  value={form.purchasePrice}
                  onChange={(e) => handleChange('purchasePrice', e.target.value)}
                  placeholder="0.00"
                  required
                />
                <Input
                  label="Prix de vente"
                  type="number"
                  value={form.sellingPrice}
                  onChange={(e) => handleChange('sellingPrice', e.target.value)}
                  placeholder="0.00"
                  required
                />
              </div>
            </Card>

            {/* Label preview */}
            <Card title="Etiquette">
              <div className="flex flex-col sm:flex-row gap-4 items-start">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowLabel(true)}
                >
                  Generer etiquette
                </Button>
                {showLabel && form.name && form.sellingPrice && (
                  <div className="border-2 border-dashed border-pink rounded-lg p-4 w-full sm:w-64">
                    <p className="font-serif text-lg font-bold text-pink text-center">Vintiz</p>
                    <hr className="my-2 border-pink-200" />
                    <p className="text-sm font-medium text-center">{form.name}</p>
                    {form.size && <p className="text-xs text-gray-500 text-center">Taille: {form.size}</p>}
                    <p className="text-lg font-bold text-teal text-center mt-2">{form.sellingPrice}&nbsp;&euro;</p>
                  </div>
                )}
              </div>
            </Card>

            {/* Actions */}
            <div className="flex gap-4 justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
              >
                Annuler
              </Button>
              <Button type="submit" size="lg">
                Enregistrer
              </Button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}
