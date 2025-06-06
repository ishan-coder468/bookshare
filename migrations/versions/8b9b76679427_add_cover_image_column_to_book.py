"""Add cover_image column to Book

Revision ID: 8b9b76679427
Revises: 
Create Date: 2025-04-09 22:10:08.047599

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b9b76679427'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('gmail', sa.String(length=150), nullable=False),
    sa.Column('password_hash', sa.String(length=150), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=True),
    sa.Column('class_name', sa.String(length=10), nullable=True),
    sa.Column('division', sa.String(length=10), nullable=True),
    sa.Column('roll_no', sa.String(length=10), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('gmail')
    )
    op.create_table('book',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('author', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('is_borrowed', sa.Boolean(), nullable=True),
    sa.Column('borrower_id', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.DateTime(), nullable=True),
    sa.Column('cover_image', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['borrower_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('favorites',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('book_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['book_id'], ['book.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('favorites')
    op.drop_table('book')
    op.drop_table('user')
    # ### end Alembic commands ###
