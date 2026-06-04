'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface Category {
  id: string;
  name: string;
}

export default function NewPermanentItemPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [name, setName] = useState('');
  const [barcode, setBarcode] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [salePrice, setSalePrice] = useState('');
  const [tvaRate, setTvaRate] = useState('20');
  const [availableFrom, setAvailableFrom] = useState('');
  const [description, setDescription] = useState('');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  useEffect(() => {
    api.get('/api/inventory/categories').then(async (res) => {
      if (res.ok) {
        const data = await res.json();
        setCategories(data);
        if (data.length > 0 && !categoryId) setCategoryId(data[0].id);
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onPhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setPhotoFile(f);
    const reader = new FileReader();
    reader.onload = () => setPhotoPreview(reader.result as string);
    reader.readAsDataURL(f);
  };

  const submit = async () => {
    setError('');
    const price = parseFloat(salePrice.replace(',', '.'));
    if (!name.trim()) {
      setError('Nom obligatoire');
      return;
    }
    if (!categoryId) {
      setError('Catégorie obligatoire');
      return;
    }
    if (!Number.isFinite(price) || price < 0) {
      setError('Prix de vente invalide');
      return;
    }
    setSubmitting(true);
    try {
      const tva = parseFloat(tvaRate.replace(',', '.'));
      const res = await api.post('/api/inventory/permanent', {
        name: name.trim(),
        barcode: barcode.trim() || undefined,
        category_id: categoryId,
        sale_price: price,
        tva_rate: Number.isFinite(tva) ? tva : 20,
        available_from: availableFrom
          ? new Date(availableFrom).toISOString()
          : null,
        description: description.trim() || null,
        is_active: true,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Erreur lors de la création');
        setSubmitting(false);
        return;
      }
      const created = await res.json();

      // Upload photo as second step (multipart) if provided
      if (photoFile) {
        const fd = new FormData();
        fd.append('file', photoFile);
        await api.upload(`/api/inventory/permanent/${created.id}/photo`, fd);
      }

      router.push(`/inventory/permanent/${created.id}`);
    } catch (e) {
      setError('Erreur réseau');
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center gap-3 mb-6">
            <Link
              href="/inventory/permanent"
              className="text-vz-ink-mute hover:text-vz-ink text-sm"
            >
              ← Retour
            </Link>
            <h1 className="text-2xl font-display font-semibold text-vz-ink">
              Nouvel article permanent
            </h1>
          </div>

          <Card>
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                  Nom de l'article *
                </label>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="ex : Sac réutilisable Vintiz"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                    Catégorie *
                  </label>
                  <select
                    value={categoryId}
                    onChange={(e) => setCategoryId(e.target.value)}
                    className="w-full px-3 py-2 rounded border border-vz-line bg-white text-vz-ink text-sm"
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                    Code-barres
                  </label>
                  <Input
                    type="text"
                    value={barcode}
                    onChange={(e) => setBarcode(e.target.value)}
                    placeholder="Auto si vide"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                    Prix de vente (€) *
                  </label>
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={salePrice}
                    onChange={(e) => setSalePrice(e.target.value)}
                    placeholder="ex : 4,90"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                    TVA (%)
                  </label>
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={tvaRate}
                    onChange={(e) => setTvaRate(e.target.value)}
                    placeholder="20"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                  Date de mise en vente
                </label>
                <Input
                  type="date"
                  value={availableFrom}
                  onChange={(e) => setAvailableFrom(e.target.value)}
                />
                <p className="text-xs text-vz-ink-mute mt-1">
                  Laisser vide pour rendre l'article scannable immédiatement.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                  Photo
                </label>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={onPhotoChange}
                  className="block w-full text-sm text-vz-ink-soft file:mr-3 file:py-2 file:px-4 file:rounded file:border-0 file:bg-vz-teal file:text-white file:text-sm file:font-medium hover:file:bg-vz-teal-deep file:cursor-pointer"
                />
                {photoPreview && (
                  <img
                    src={photoPreview}
                    alt="Aperçu"
                    className="mt-3 h-40 w-40 object-cover rounded border border-vz-line"
                  />
                )}
                <p className="text-xs text-vz-ink-mute mt-1.5">
                  La copie vitrine (fond détouré + canvas Vintiz) est générée
                  automatiquement après l'upload, si un backend de détourage est
                  configuré.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-vz-ink-soft mb-1.5">
                  Description (optionnel)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 rounded border border-vz-line bg-white text-vz-ink text-sm"
                  placeholder="Notes internes, dimensions, usage…"
                />
              </div>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{error}</p>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-vz-line">
                <Link href="/inventory/permanent">
                  <Button variant="outline">Annuler</Button>
                </Link>
                <Button onClick={submit} disabled={submitting}>
                  {submitting ? 'Création…' : "Créer l'article"}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
